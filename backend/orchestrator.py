"""ASSO Orchestration Controller — takes automated corrective action based on ML predictions"""
import asyncio
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Optional
import httpx
from sqlalchemy import select, desc, and_, func

from database import async_session
from models import Service, Prediction, Action, Metric, ComparisonRun
from websocket_manager import ws_manager
from config import Config

logger = logging.getLogger("asso.orchestrator")


class Orchestrator:
    """
    Monitors ML predictions and takes graduated corrective action:
    - Risk 70-80:  Rate-limit (moderate throttle)
    - Risk 80-90:  Queue reduction + stronger throttle
    - Risk 90+:    Aggressive throttle + load shedding

    When risk drops below 50, gradually relaxes restrictions.
    Can be toggled ON/OFF for before/after comparison.
    """

    def __init__(self):
        self.running = False
        self.enabled = True
        self._task = None
        self._http_client = None
        self._service_states: dict[str, dict] = {}  # Track current throttle state per service
        self._cooldown: dict[str, float] = {}  # Prevent action spam
        self.start_time = None
        self._comparison_run_id: Optional[str] = None

    async def start(self):
        self.running = True
        self.start_time = time.monotonic()
        self._http_client = httpx.AsyncClient(timeout=3.0)
        self._task = asyncio.create_task(self._orchestrate_loop())
        logger.info("Orchestrator started (enabled=%s)", self.enabled)

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
        logger.info("Orchestrator stopped")

    def toggle(self, enabled: bool):
        self.enabled = enabled
        logger.info("Orchestrator %s", "ENABLED" if enabled else "DISABLED")
        if not enabled:
            # Reset all throttles when disabled
            asyncio.create_task(self._reset_all_throttles())

    async def _orchestrate_loop(self):
        while self.running:
            try:
                await self._evaluate_and_act()
                await asyncio.sleep(2.0)  # Check every 2 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Orchestration error: %s", e)
                await asyncio.sleep(2)

    async def _evaluate_and_act(self):
        """Evaluate latest predictions and take action if needed"""
        async with async_session() as session:
            result = await session.execute(select(Service).where(Service.status == "healthy"))
            services = result.scalars().all()

        for service in services:
            await self._evaluate_service(service)

    async def _evaluate_service(self, service: Service):
        """Evaluate predictions for a single service and take action"""
        # Get latest predictions for this service
        async with async_session() as session:
            result = await session.execute(
                select(Prediction)
                .where(and_(
                    Prediction.service_id == service.id,
                    Prediction.timestamp >= datetime.utcnow() - timedelta(seconds=10)
                ))
                .order_by(desc(Prediction.timestamp))
                .limit(4)  # One per metric type
            )
            predictions = result.scalars().all()

        if not predictions:
            return

        # Find the highest risk prediction
        max_pred = max(predictions, key=lambda p: p.risk_score)
        risk_score = max_pred.risk_score

        # Check cooldown (don't spam actions)
        last_action_time = self._cooldown.get(service.id, 0)
        if time.monotonic() - last_action_time < 5.0:  # 5-second cooldown
            return

        current_state = self._service_states.get(service.id, {"level": "normal", "max_rps": Config.DEFAULT_MAX_RPS})

        if self.enabled:
            if risk_score >= Config.RISK_CRITICAL and current_state["level"] != "critical":
                await self._take_action(service, "critical_throttle", max_pred,
                                        max_rps=Config.THROTTLED_RPS_CRITICAL)
            elif risk_score >= Config.RISK_HIGH and current_state["level"] not in ("critical", "high"):
                await self._take_action(service, "high_throttle", max_pred,
                                        max_rps=Config.THROTTLED_RPS_HIGH)
            elif risk_score >= Config.RISK_MODERATE and current_state["level"] not in ("critical", "high", "moderate"):
                await self._take_action(service, "rate_limit", max_pred,
                                        max_rps=Config.THROTTLED_RPS_MODERATE)
            elif risk_score < Config.RISK_LOW and current_state["level"] != "normal":
                await self._take_action(service, "relax", max_pred,
                                        max_rps=Config.DEFAULT_MAX_RPS)
        else:
            # ASSO disabled — log the prediction but take no action
            if risk_score >= Config.RISK_MODERATE:
                await self._log_action(service, "prediction_only",
                    f"Risk {risk_score:.0f} for {max_pred.metric_type} (ASSO disabled, no action taken)",
                    json.dumps({"risk_score": risk_score, "predicted_breach": max_pred.predicted_breach_time}),
                    "skipped"
                )

    async def _take_action(self, service: Service, action_type: str,
                            prediction: Prediction, max_rps: int):
        """Execute a corrective action against a target service"""
        level_map = {
            "critical_throttle": "critical",
            "high_throttle": "high",
            "rate_limit": "moderate",
            "relax": "normal",
        }

        reason = self._build_reason(action_type, prediction)
        details = json.dumps({
            "risk_score": round(prediction.risk_score, 1),
            "metric_type": prediction.metric_type,
            "current_value": round(prediction.current_value, 2) if prediction.current_value else 0,
            "predicted_value": round(prediction.predicted_value, 2) if prediction.predicted_value else 0,
            "breach_time": prediction.predicted_breach_time,
            "max_rps": max_rps,
        })

        # Send configuration to the target app
        result = "success"
        try:
            url = f"http://{service.host}:{service.port}{service.configure_path}"
            resp = await self._http_client.post(url, json={
                "max_rps": max_rps,
                "action": action_type,
            })
            if resp.status_code != 200:
                result = f"http_error_{resp.status_code}"
        except Exception as e:
            result = f"error: {str(e)[:100]}"
            logger.warning("Failed to configure %s: %s", service.name, e)

        # Update state
        self._service_states[service.id] = {"level": level_map.get(action_type, "normal"), "max_rps": max_rps}
        self._cooldown[service.id] = time.monotonic()

        # Log the action
        await self._log_action(service, action_type, reason, details, result)

        logger.info("ACTION: %s on %s — %s (result: %s)", action_type, service.name, reason, result)

    async def _log_action(self, service: Service, action_type: str,
                           reason: str, details: str, result: str):
        """Log an action to the database and broadcast via WebSocket"""
        action = Action(
            timestamp=datetime.utcnow(),
            service_id=service.id,
            action_type=action_type,
            reason=reason,
            details=details,
            result=result,
            asso_enabled=self.enabled,
        )

        async with async_session() as session:
            session.add(action)
            await session.commit()

        await ws_manager.broadcast("action", {
            "id": action.id,
            "timestamp": action.timestamp.isoformat(),
            "service_id": service.id,
            "service_name": service.name,
            "action_type": action_type,
            "reason": reason,
            "details": details,
            "result": result,
            "asso_enabled": self.enabled,
        })

    @staticmethod
    def _build_reason(action_type: str, prediction: Prediction) -> str:
        """Build a human-readable reason string"""
        metric_labels = {
            "cpu_percent": "CPU",
            "memory_percent": "Memory",
            "latency_ms": "Latency",
            "queue_length": "Queue depth",
        }
        metric_label = metric_labels.get(prediction.metric_type, prediction.metric_type)
        breach_str = f" in {prediction.predicted_breach_time}s" if prediction.predicted_breach_time else ""

        if action_type == "relax":
            return f"Risk decreased — relaxing throttle (risk={prediction.risk_score:.0f})"
        elif action_type == "rate_limit":
            return (f"Predicted {metric_label} breach{breach_str} — "
                    f"applying rate limit (risk={prediction.risk_score:.0f})")
        elif action_type == "high_throttle":
            return (f"High {metric_label} risk{breach_str} — "
                    f"aggressive throttle (risk={prediction.risk_score:.0f})")
        elif action_type == "critical_throttle":
            return (f"CRITICAL {metric_label} alert{breach_str} — "
                    f"emergency load shedding (risk={prediction.risk_score:.0f})")
        return f"{action_type}: risk={prediction.risk_score:.0f}"

    async def _reset_all_throttles(self):
        """Reset all services to default rate limits"""
        async with async_session() as session:
            result = await session.execute(select(Service))
            services = result.scalars().all()

        for service in services:
            try:
                url = f"http://{service.host}:{service.port}{service.configure_path}"
                await self._http_client.post(url, json={
                    "max_rps": Config.DEFAULT_MAX_RPS,
                    "action": "reset",
                })
                self._service_states[service.id] = {"level": "normal", "max_rps": Config.DEFAULT_MAX_RPS}
            except Exception:
                pass

    async def start_comparison_run(self, run_id: str, asso_enabled: bool):
        """Start tracking a comparison run"""
        self._comparison_run_id = run_id
        run = ComparisonRun(
            run_id=run_id,
            asso_enabled=asso_enabled,
            start_time=datetime.utcnow(),
        )
        async with async_session() as session:
            session.add(run)
            await session.commit()
        return run

    async def end_comparison_run(self, run_id: str):
        """End a comparison run and compute summary stats"""
        async with async_session() as session:
            result = await session.execute(
                select(ComparisonRun).where(ComparisonRun.run_id == run_id)
            )
            run = result.scalars().first()
            if not run:
                return None

            run.end_time = datetime.utcnow()

            # Compute stats from metrics during the run
            metrics_result = await session.execute(
                select(Metric).where(and_(
                    Metric.timestamp >= run.start_time,
                    Metric.timestamp <= run.end_time,
                ))
            )
            metrics = metrics_result.scalars().all()

            if metrics:
                run.peak_cpu = max(m.cpu_percent for m in metrics)
                run.peak_memory = max(m.memory_percent for m in metrics)
                run.peak_latency = max(m.latency_ms for m in metrics)
                latencies = [m.latency_ms for m in metrics if m.latency_ms > 0]
                run.avg_latency = sum(latencies) / len(latencies) if latencies else 0
                run.total_requests = sum(int(m.request_rate) for m in metrics)
                run.error_count = sum(1 for m in metrics if m.error_rate > 0.1)
                run.breach_count = sum(
                    1 for m in metrics
                    if m.cpu_percent > Config.CPU_CRITICAL
                    or m.memory_percent > Config.MEMORY_CRITICAL
                    or m.latency_ms > Config.LATENCY_CRITICAL
                )

            await session.commit()
            return run

        self._comparison_run_id = None


# Global singleton
orchestrator = Orchestrator()

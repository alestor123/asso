"""
ASSO — Adaptive Service Stability Orchestrator
Main FastAPI Application

Real-time infrastructure monitoring + ML-based predictive auto-scaling.
"""
import asyncio
import uuid
import time
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc, and_, func

from config import Config
from database import init_db, async_session
from models import Service, Metric, Prediction, Action, ComparisonRun
from schemas import (
    ServiceOut, MetricOut, PredictionOut, ActionOut,
    RiskScoreOut, AssoStatus, ComparisonRunOut, ComparisonResult,
    ToggleRequest, PredictionStats, WSMessage,
)
from websocket_manager import ws_manager
from collector import collector
from forecaster import forecaster
from orchestrator import orchestrator

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("asso")

START_TIME = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: start and stop background services"""
    logger.info("═══════════════════════════════════════════════════")
    logger.info("  ASSO — Adaptive Service Stability Orchestrator  ")
    logger.info("═══════════════════════════════════════════════════")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Register configured services
    await _register_services()

    # Start background tasks
    await collector.start()
    await forecaster.start()
    await orchestrator.start()

    # Start periodic prediction validation
    validation_task = asyncio.create_task(_periodic_validation())

    logger.info("All systems operational — monitoring %d services", len(Config.SERVICES))

    yield

    # Shutdown
    validation_task.cancel()
    await collector.stop()
    await forecaster.stop()
    await orchestrator.stop()
    logger.info("ASSO shutdown complete")


app = FastAPI(
    title="ASSO — Adaptive Service Stability Orchestrator",
    description="Real-time infrastructure monitoring and predictive auto-scaling system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────── Helper Functions ────────────────

async def _register_services():
    """Register configured services in the database"""
    async with async_session() as session:
        for svc_config in Config.SERVICES:
            existing = await session.get(Service, svc_config["id"])
            if not existing:
                service = Service(
                    id=svc_config["id"],
                    name=svc_config["name"],
                    host=svc_config["host"],
                    port=svc_config["port"],
                    service_type=svc_config["service_type"],
                    metrics_path=svc_config.get("metrics_path", "/metrics"),
                    health_path=svc_config.get("health_path", "/health"),
                    configure_path=svc_config.get("configure_path", "/configure"),
                    status="unknown",
                )
                session.add(service)
                logger.info("Registered service: %s (%s:%d)",
                           svc_config["name"], svc_config["host"], svc_config["port"])
            else:
                existing.host = svc_config["host"]
                existing.port = svc_config["port"]
                existing.metrics_path = svc_config.get("metrics_path", "/metrics")
                existing.health_path = svc_config.get("health_path", "/health")
                existing.configure_path = svc_config.get("configure_path", "/configure")
        await session.commit()


async def _periodic_validation():
    """Periodically validate past predictions against actual outcomes"""
    while True:
        try:
            await asyncio.sleep(30)  # Every 30 seconds
            await forecaster.validate_past_predictions()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Validation error: %s", e)


# ──────────────── REST API Endpoints ────────────────

@app.get("/api/services", response_model=list[ServiceOut])
async def get_services():
    """List all monitored services"""
    async with async_session() as session:
        result = await session.execute(select(Service).order_by(Service.name))
        services = result.scalars().all()
        return [ServiceOut.model_validate(s) for s in services]


@app.get("/api/services/{service_id}/metrics", response_model=list[MetricOut])
async def get_service_metrics(service_id: str, window: int = Query(default=120, ge=10, le=600)):
    """Get recent metrics for a service"""
    cutoff = datetime.utcnow() - timedelta(seconds=window)
    async with async_session() as session:
        result = await session.execute(
            select(Metric)
            .where(and_(Metric.service_id == service_id, Metric.timestamp >= cutoff))
            .order_by(Metric.timestamp.asc())
        )
        metrics = result.scalars().all()
        return [MetricOut.model_validate(m) for m in metrics]


@app.get("/api/services/{service_id}/predictions", response_model=list[PredictionOut])
async def get_service_predictions(service_id: str, window: int = Query(default=120, ge=10, le=600)):
    """Get recent predictions for a service"""
    cutoff = datetime.utcnow() - timedelta(seconds=window)
    async with async_session() as session:
        result = await session.execute(
            select(Prediction)
            .where(and_(Prediction.service_id == service_id, Prediction.timestamp >= cutoff))
            .order_by(Prediction.timestamp.asc())
        )
        predictions = result.scalars().all()
        return [PredictionOut.model_validate(p) for p in predictions]


@app.get("/api/actions", response_model=list[ActionOut])
async def get_actions(limit: int = Query(default=50, ge=1, le=200)):
    """Get recent orchestration actions"""
    async with async_session() as session:
        result = await session.execute(
            select(Action).order_by(desc(Action.timestamp)).limit(limit)
        )
        actions = result.scalars().all()
        return [ActionOut.model_validate(a) for a in reversed(actions)]


@app.get("/api/risk", response_model=list[RiskScoreOut])
async def get_risk_scores():
    """Get current risk scores for all services"""
    risk_scores = []
    async with async_session() as session:
        services_result = await session.execute(select(Service))
        services = services_result.scalars().all()

        for service in services:
            # Get latest prediction with highest risk
            result = await session.execute(
                select(Prediction)
                .where(and_(
                    Prediction.service_id == service.id,
                    Prediction.timestamp >= datetime.utcnow() - timedelta(seconds=10)
                ))
                .order_by(desc(Prediction.risk_score))
                .limit(1)
            )
            pred = result.scalars().first()

            if pred:
                risk_level = "low"
                if pred.risk_score >= Config.RISK_CRITICAL:
                    risk_level = "critical"
                elif pred.risk_score >= Config.RISK_HIGH:
                    risk_level = "high"
                elif pred.risk_score >= Config.RISK_MODERATE:
                    risk_level = "moderate"

                risk_scores.append(RiskScoreOut(
                    service_id=service.id,
                    service_name=service.name,
                    risk_score=round(pred.risk_score, 1),
                    risk_level=risk_level,
                    predicted_breach_time=pred.predicted_breach_time,
                    metric_type=pred.metric_type,
                    current_value=round(pred.current_value, 2) if pred.current_value else 0,
                    predicted_value=round(pred.predicted_value, 2) if pred.predicted_value else 0,
                    confidence=round(pred.confidence, 3) if pred.confidence else 0,
                ))
            else:
                risk_scores.append(RiskScoreOut(
                    service_id=service.id,
                    service_name=service.name,
                    risk_score=0,
                    risk_level="low",
                ))

    return risk_scores


@app.post("/api/asso/toggle")
async def toggle_asso(request: ToggleRequest):
    """Enable or disable ASSO orchestration"""
    orchestrator.toggle(request.enabled)
    return {"status": "ok", "enabled": request.enabled}


@app.get("/api/asso/status", response_model=AssoStatus)
async def get_asso_status():
    """Get current ASSO system status"""
    async with async_session() as session:
        pred_count = (await session.execute(
            select(func.count(Prediction.id))
        )).scalar() or 0

        action_count = (await session.execute(
            select(func.count(Action.id))
        )).scalar() or 0

        correct_count = (await session.execute(
            select(func.count(Prediction.id))
            .where(Prediction.was_correct == True)
        )).scalar() or 0

        validated_count = (await session.execute(
            select(func.count(Prediction.id))
            .where(Prediction.was_correct.isnot(None))
        )).scalar() or 0

        service_count = (await session.execute(
            select(func.count(Service.id))
        )).scalar() or 0

    accuracy = (correct_count / validated_count * 100) if validated_count > 0 else 0

    return AssoStatus(
        enabled=orchestrator.enabled,
        total_predictions=pred_count,
        total_actions=action_count,
        accuracy=round(accuracy, 1),
        uptime_seconds=round(time.monotonic() - START_TIME, 1),
        services_monitored=service_count,
    )


@app.get("/api/stats", response_model=PredictionStats)
async def get_prediction_stats():
    """Get prediction accuracy statistics"""
    async with async_session() as session:
        total = (await session.execute(
            select(func.count(Prediction.id)).where(Prediction.was_correct.isnot(None))
        )).scalar() or 0

        correct = (await session.execute(
            select(func.count(Prediction.id)).where(Prediction.was_correct == True)
        )).scalar() or 0

        false_positives = (await session.execute(
            select(func.count(Prediction.id)).where(
                and_(Prediction.was_correct == False, Prediction.risk_score >= Config.RISK_MODERATE)
            )
        )).scalar() or 0

        # Per-metric breakdown
        breakdown = {}
        for metric_type in ["cpu_percent", "memory_percent", "latency_ms", "queue_length"]:
            mt = (await session.execute(
                select(func.count(Prediction.id))
                .where(and_(Prediction.metric_type == metric_type, Prediction.was_correct.isnot(None)))
            )).scalar() or 0
            mc = (await session.execute(
                select(func.count(Prediction.id))
                .where(and_(Prediction.metric_type == metric_type, Prediction.was_correct == True))
            )).scalar() or 0
            breakdown[metric_type] = {
                "total": mt,
                "correct": mc,
                "accuracy": round(mc / mt * 100, 1) if mt > 0 else 0
            }

    return PredictionStats(
        total_predictions=total,
        correct_predictions=correct,
        accuracy=round(correct / total * 100, 1) if total > 0 else 0,
        false_positive_rate=round(false_positives / total * 100, 1) if total > 0 else 0,
        avg_response_time_ms=0,  # Computed elsewhere
        predictions_by_metric=breakdown,
    )


@app.post("/api/comparison/start")
async def start_comparison(asso_enabled: bool = Query(default=True)):
    """Start a comparison run"""
    run_id = str(uuid.uuid4())[:8]
    orchestrator.toggle(asso_enabled)
    await orchestrator.start_comparison_run(run_id, asso_enabled)
    return {"run_id": run_id, "asso_enabled": asso_enabled, "status": "started"}


@app.post("/api/comparison/end")
async def end_comparison(run_id: str = Query(...)):
    """End a comparison run and get summary"""
    run = await orchestrator.end_comparison_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return ComparisonRunOut.model_validate(run)


@app.get("/api/comparison/results")
async def get_comparison_results():
    """Get all comparison run results"""
    async with async_session() as session:
        result = await session.execute(
            select(ComparisonRun).order_by(desc(ComparisonRun.start_time)).limit(20)
        )
        runs = result.scalars().all()
        return [ComparisonRunOut.model_validate(r) for r in runs]


@app.get("/api/metrics/all")
async def get_all_metrics(window: int = Query(default=120, ge=10, le=600)):
    """Get recent metrics for all services"""
    cutoff = datetime.utcnow() - timedelta(seconds=window)
    async with async_session() as session:
        result = await session.execute(
            select(Metric)
            .where(Metric.timestamp >= cutoff)
            .order_by(Metric.timestamp.asc())
        )
        metrics = result.scalars().all()
        return [MetricOut.model_validate(m) for m in metrics]


# ──────────────── WebSocket Endpoint ────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await ws_manager.connect(websocket)
    try:
        # Send initial state
        services = await get_services()
        await ws_manager.send_personal(websocket, "init", {
            "services": [s.model_dump() for s in services],
            "asso_enabled": orchestrator.enabled,
        })

        # Keep connection alive and listen for client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle client commands (e.g., toggle ASSO)
                import json
                msg = json.loads(data)
                if msg.get("type") == "toggle_asso":
                    orchestrator.toggle(msg.get("enabled", True))
                    await ws_manager.broadcast("status", {"asso_enabled": orchestrator.enabled})
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text('{"type":"ping"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(websocket)


# ──────────────── Health Check ────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "uptime": round(time.monotonic() - START_TIME, 1),
        "services": len(Config.SERVICES),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")

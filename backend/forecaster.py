"""ASSO ML Forecasting Engine — predicts resource exhaustion 30-90 seconds ahead using numpy-only implementations"""
import asyncio
import time
import logging
import math
from datetime import datetime, timedelta
from typing import Optional
import numpy as np
from sqlalchemy import select, desc, and_

from database import async_session
from models import Metric, Prediction, Service
from websocket_manager import ws_manager
from config import Config

logger = logging.getLogger("asso.forecaster")


class TimeSeriesForecaster:
    """
    Lightweight ML forecasting using:
    - Exponential Weighted Moving Average (EWMA) for trend estimation
    - Linear Regression (numpy) for trajectory projection
    - Z-score anomaly detection
    - Composite risk scoring

    No heavy dependencies (scikit-learn/Prophet) needed — just numpy.
    This is justified because for 30-90 second horizons on system metrics,
    simple trend extrapolation outperforms complex models while being fully explainable.
    """

    THRESHOLDS = {
        "cpu_percent":    (Config.CPU_WARNING, Config.CPU_CRITICAL),
        "memory_percent": (Config.MEMORY_WARNING, Config.MEMORY_CRITICAL),
        "latency_ms":     (Config.LATENCY_WARNING, Config.LATENCY_CRITICAL),
        "queue_length":   (Config.QUEUE_WARNING, Config.QUEUE_CRITICAL),
    }

    def __init__(self):
        self.running = False
        self._task = None

    async def start(self):
        self.running = True
        self._task = asyncio.create_task(self._forecast_loop())
        logger.info("Forecaster started (interval=%.1fs, horizon=%ds)",
                     Config.FORECAST_INTERVAL, Config.FORECAST_HORIZON)

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Forecaster stopped")

    async def _forecast_loop(self):
        while self.running:
            try:
                start = time.monotonic()
                await self._forecast_all_services()
                elapsed = time.monotonic() - start
                sleep_time = max(0.5, Config.FORECAST_INTERVAL - elapsed)
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Forecast error: %s", e)
                await asyncio.sleep(2)

    async def _forecast_all_services(self):
        async with async_session() as session:
            result = await session.execute(select(Service).where(Service.status == "healthy"))
            services = result.scalars().all()

        for service in services:
            await self._forecast_service(service)

    async def _forecast_service(self, service: Service):
        """Generate predictions for all monitored metrics of a service"""
        # Fetch recent metric history
        cutoff = datetime.utcnow() - timedelta(seconds=Config.HISTORY_WINDOW)
        async with async_session() as session:
            result = await session.execute(
                select(Metric)
                .where(and_(Metric.service_id == service.id, Metric.timestamp >= cutoff))
                .order_by(Metric.timestamp.asc())
            )
            metrics = result.scalars().all()

        if len(metrics) < 10:
            return  # Not enough data for meaningful prediction

        # Extract time-series arrays
        timestamps = np.array([(m.timestamp - metrics[0].timestamp).total_seconds() for m in metrics])

        metric_series = {
            "cpu_percent":    np.array([m.cpu_percent for m in metrics]),
            "memory_percent": np.array([m.memory_percent for m in metrics]),
            "latency_ms":     np.array([m.latency_ms for m in metrics]),
            "queue_length":   np.array([float(m.queue_length) for m in metrics]),
        }

        max_risk_score = 0.0
        max_risk_metric = ""
        max_breach_time = None

        for metric_name, values in metric_series.items():
            if metric_name not in self.THRESHOLDS:
                continue

            warning_thresh, critical_thresh = self.THRESHOLDS[metric_name]

            # Skip if metric is consistently near zero (not meaningful)
            if np.max(values) < 1.0 and metric_name not in ("memory_percent", "cpu_percent"):
                continue

            # --- Linear Regression for trend ---
            predicted_value, slope, confidence = self._linear_forecast(
                timestamps, values, Config.FORECAST_HORIZON
            )

            # --- Exponential Smoothing for smoothed current ---
            smoothed_current = self._ewma(values, alpha=0.3)[-1]

            # --- Anomaly detection (Z-score) ---
            is_anomaly, z_score = self._zscore_anomaly(values, threshold=2.5)

            # --- Calculate time to breach ---
            breach_time = self._time_to_breach(
                smoothed_current, slope, critical_thresh, timestamps
            )

            # --- Composite risk score ---
            risk_score = self._compute_risk_score(
                current_value=smoothed_current,
                predicted_value=predicted_value,
                warning_thresh=warning_thresh,
                critical_thresh=critical_thresh,
                slope=slope,
                breach_time=breach_time,
                is_anomaly=is_anomaly,
                z_score=z_score,
            )

            # Store prediction
            prediction = Prediction(
                timestamp=datetime.utcnow(),
                service_id=service.id,
                metric_type=metric_name,
                current_value=float(smoothed_current),
                predicted_value=float(predicted_value),
                predicted_breach_time=breach_time,
                confidence=float(confidence),
                risk_score=float(risk_score),
            )

            async with async_session() as session:
                session.add(prediction)
                await session.commit()

            if risk_score > max_risk_score:
                max_risk_score = risk_score
                max_risk_metric = metric_name
                max_breach_time = breach_time

            # Broadcast prediction
            await ws_manager.broadcast("prediction", {
                "service_id": service.id,
                "service_name": service.name,
                "metric_type": metric_name,
                "current_value": round(float(smoothed_current), 2),
                "predicted_value": round(float(predicted_value), 2),
                "predicted_breach_time": breach_time,
                "confidence": round(float(confidence), 3),
                "risk_score": round(float(risk_score), 1),
                "is_anomaly": bool(is_anomaly),
                "slope": round(float(slope), 4),
            })

        # Broadcast overall risk for this service
        risk_level = "low"
        if max_risk_score >= Config.RISK_CRITICAL:
            risk_level = "critical"
        elif max_risk_score >= Config.RISK_HIGH:
            risk_level = "high"
        elif max_risk_score >= Config.RISK_MODERATE:
            risk_level = "moderate"

        await ws_manager.broadcast("risk", {
            "service_id": service.id,
            "service_name": service.name,
            "risk_score": round(max_risk_score, 1),
            "risk_level": risk_level,
            "metric_type": max_risk_metric,
            "predicted_breach_time": max_breach_time,
        })

    @staticmethod
    def _linear_forecast(timestamps: np.ndarray, values: np.ndarray,
                          horizon: int) -> tuple[float, float, float]:
        """
        Linear regression forecast.
        Returns: (predicted_value_at_horizon, slope_per_second, confidence)
        """
        n = len(timestamps)
        if n < 2:
            return float(values[-1]), 0.0, 0.0

        # Use recent window (last 30s or all data, whichever is smaller)
        window_size = min(n, max(20, n // 2))
        t = timestamps[-window_size:]
        v = values[-window_size:]

        # Normalize time
        t_norm = t - t[0]

        # Linear regression: y = a + b*t
        t_mean = np.mean(t_norm)
        v_mean = np.mean(v)
        ss_tt = np.sum((t_norm - t_mean) ** 2)

        if ss_tt < 1e-10:
            return float(v_mean), 0.0, 0.5

        slope = np.sum((t_norm - t_mean) * (v - v_mean)) / ss_tt
        intercept = v_mean - slope * t_mean

        # Predict at horizon
        future_t = t_norm[-1] + horizon
        predicted = intercept + slope * future_t

        # R² for confidence
        v_pred = intercept + slope * t_norm
        ss_res = np.sum((v - v_pred) ** 2)
        ss_tot = np.sum((v - v_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 1e-10 else 0.0
        confidence = max(0.0, min(1.0, r_squared))

        return float(predicted), float(slope), float(confidence)

    @staticmethod
    def _ewma(values: np.ndarray, alpha: float = 0.3) -> np.ndarray:
        """Exponential Weighted Moving Average"""
        result = np.zeros_like(values, dtype=float)
        result[0] = values[0]
        for i in range(1, len(values)):
            result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
        return result

    @staticmethod
    def _zscore_anomaly(values: np.ndarray, threshold: float = 2.5) -> tuple[bool, float]:
        """Detect if the latest value is an anomaly using z-score"""
        if len(values) < 5:
            return False, 0.0
        mean = np.mean(values[:-1])
        std = np.std(values[:-1])
        if std < 1e-10:
            return False, 0.0
        z = abs(values[-1] - mean) / std
        return bool(z > threshold), float(z)

    @staticmethod
    def _time_to_breach(current: float, slope: float, threshold: float,
                         timestamps: np.ndarray) -> Optional[int]:
        """Estimate seconds until the threshold is breached"""
        if slope <= 0 or current >= threshold:
            if current >= threshold:
                return 0
            return None  # Not trending toward breach
        remaining = threshold - current
        seconds = remaining / slope
        if seconds > 300:  # Cap at 5 minutes
            return None
        return max(1, int(seconds))

    @staticmethod
    def _compute_risk_score(current_value: float, predicted_value: float,
                             warning_thresh: float, critical_thresh: float,
                             slope: float, breach_time: Optional[int],
                             is_anomaly: bool, z_score: float) -> float:
        """
        Compute a composite risk score (0-100).

        Components:
        - Proximity to threshold (0-35): how close current value is to critical
        - Trend severity (0-25): how steep the upward trend is
        - Time to breach (0-25): inverse of time remaining before breach
        - Anomaly bonus (0-15): extra risk if current pattern is anomalous
        """
        # Proximity score (0-35)
        if current_value >= critical_thresh:
            proximity = 35.0
        elif current_value >= warning_thresh:
            ratio = (current_value - warning_thresh) / max(1, critical_thresh - warning_thresh)
            proximity = 15 + ratio * 20
        else:
            ratio = current_value / max(1, warning_thresh)
            proximity = ratio * 15
        proximity = min(35, max(0, proximity))

        # Trend score (0-25)
        if slope > 0:
            # Normalize slope relative to threshold range
            threshold_range = max(1, critical_thresh - warning_thresh)
            normalized_slope = min(1.0, (slope * 10) / threshold_range)  # slope per 10 seconds
            trend = normalized_slope * 25
        else:
            trend = 0.0
        trend = min(25, max(0, trend))

        # Time-to-breach score (0-25)
        if breach_time is not None:
            if breach_time <= 0:
                ttb_score = 25.0
            elif breach_time <= 30:
                ttb_score = 25 * (1 - breach_time / 30)
            elif breach_time <= 90:
                ttb_score = 15 * (1 - (breach_time - 30) / 60)
            else:
                ttb_score = max(0, 5 * (1 - (breach_time - 90) / 210))
        else:
            ttb_score = 0.0
        ttb_score = min(25, max(0, ttb_score))

        # Anomaly score (0-15)
        if is_anomaly:
            anomaly_score = min(15, z_score * 3)
        else:
            anomaly_score = 0.0
        anomaly_score = min(15, max(0, anomaly_score))

        total = proximity + trend + ttb_score + anomaly_score
        return min(100.0, max(0.0, total))

    async def validate_past_predictions(self):
        """
        Backfill actual_value and was_correct for past predictions.
        This runs periodically to build the accuracy dashboard.
        """
        cutoff = datetime.utcnow() - timedelta(seconds=Config.FORECAST_HORIZON + 10)
        async with async_session() as session:
            result = await session.execute(
                select(Prediction)
                .where(and_(
                    Prediction.actual_value.is_(None),
                    Prediction.timestamp <= cutoff
                ))
                .limit(100)
            )
            predictions = result.scalars().all()

            for pred in predictions:
                # Find the actual metric value at the predicted time
                target_time = pred.timestamp + timedelta(seconds=Config.FORECAST_HORIZON)
                actual_result = await session.execute(
                    select(Metric)
                    .where(and_(
                        Metric.service_id == pred.service_id,
                        Metric.timestamp >= target_time - timedelta(seconds=5),
                        Metric.timestamp <= target_time + timedelta(seconds=5),
                    ))
                    .order_by(Metric.timestamp.asc())
                    .limit(1)
                )
                actual_metric = actual_result.scalars().first()

                if actual_metric:
                    actual_val = getattr(actual_metric, pred.metric_type, None)
                    if actual_val is not None:
                        pred.actual_value = float(actual_val)
                        # "Correct" if predicted direction was right and within 30% margin
                        if pred.predicted_value is not None:
                            pred_direction = pred.predicted_value > pred.current_value
                            actual_direction = float(actual_val) > pred.current_value
                            margin = abs(pred.predicted_value - float(actual_val))
                            threshold = max(abs(pred.predicted_value) * 0.3, 5.0)
                            pred.was_correct = (pred_direction == actual_direction) and (margin < threshold)

            await session.commit()


# Global singleton
forecaster = TimeSeriesForecaster()

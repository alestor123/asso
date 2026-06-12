"""ASSO Pydantic Schemas for API request/response validation"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# --- Service ---
class ServiceOut(BaseModel):
    id: str
    name: str
    host: str
    port: int
    service_type: Optional[str] = None
    pid: Optional[int] = None
    status: str = "unknown"

    model_config = {"from_attributes": True}


# --- Metric ---
class MetricOut(BaseModel):
    id: int
    timestamp: datetime
    service_id: str
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    request_rate: float
    latency_ms: float
    queue_length: int
    error_rate: float
    active_connections: int

    model_config = {"from_attributes": True}


# --- Prediction ---
class PredictionOut(BaseModel):
    id: int
    timestamp: datetime
    service_id: str
    metric_type: str
    current_value: Optional[float] = None
    predicted_value: Optional[float] = None
    predicted_breach_time: Optional[int] = None
    confidence: float = 0.0
    risk_score: float = 0.0
    actual_value: Optional[float] = None
    was_correct: Optional[bool] = None

    model_config = {"from_attributes": True}


# --- Action ---
class ActionOut(BaseModel):
    id: int
    timestamp: datetime
    service_id: str
    action_type: str
    reason: Optional[str] = None
    details: Optional[str] = None
    result: Optional[str] = None
    asso_enabled: bool = True

    model_config = {"from_attributes": True}


# --- Risk Score ---
class RiskScoreOut(BaseModel):
    service_id: str
    service_name: str
    risk_score: float
    risk_level: str  # low, moderate, high, critical
    predicted_breach_time: Optional[int] = None
    metric_type: str = ""
    current_value: float = 0.0
    predicted_value: float = 0.0
    confidence: float = 0.0


# --- ASSO Status ---
class AssoStatus(BaseModel):
    enabled: bool
    total_predictions: int = 0
    total_actions: int = 0
    accuracy: float = 0.0
    uptime_seconds: float = 0.0
    services_monitored: int = 0


# --- Comparison Run ---
class ComparisonRunOut(BaseModel):
    id: int
    run_id: str
    asso_enabled: bool
    start_time: datetime
    end_time: Optional[datetime] = None
    peak_cpu: float = 0.0
    peak_memory: float = 0.0
    peak_latency: float = 0.0
    avg_latency: float = 0.0
    error_count: int = 0
    total_requests: int = 0
    breach_count: int = 0

    model_config = {"from_attributes": True}


# --- Comparison Result ---
class ComparisonResult(BaseModel):
    run_id: str
    asso_on: Optional[ComparisonRunOut] = None
    asso_off: Optional[ComparisonRunOut] = None
    asso_on_metrics: List[MetricOut] = []
    asso_off_metrics: List[MetricOut] = []


# --- WebSocket Message ---
class WSMessage(BaseModel):
    type: str  # metric, prediction, risk, action, status
    data: dict


# --- Toggle Request ---
class ToggleRequest(BaseModel):
    enabled: bool


# --- Stats ---
class PredictionStats(BaseModel):
    total_predictions: int
    correct_predictions: int
    accuracy: float
    false_positive_rate: float
    avg_response_time_ms: float
    predictions_by_metric: dict

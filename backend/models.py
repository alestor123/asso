"""ASSO SQLAlchemy ORM Models"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    service_type = Column(String(50))
    pid = Column(Integer, nullable=True)
    status = Column(String(20), default="unknown")
    metrics_path = Column(String(100), default="/metrics")
    health_path = Column(String(100), default="/health")
    configure_path = Column(String(100), default="/configure")
    created_at = Column(DateTime, default=datetime.utcnow)


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False, index=True)
    cpu_percent = Column(Float, default=0.0)
    memory_mb = Column(Float, default=0.0)
    memory_percent = Column(Float, default=0.0)
    request_rate = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    queue_length = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    active_connections = Column(Integer, default=0)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)
    current_value = Column(Float)
    predicted_value = Column(Float)
    predicted_breach_time = Column(Integer)  # seconds until breach, None if no breach
    confidence = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    actual_value = Column(Float, nullable=True)  # filled later for validation
    was_correct = Column(Boolean, nullable=True)


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    reason = Column(Text)
    details = Column(Text)
    result = Column(String(50))
    asso_enabled = Column(Boolean, default=True)


class ComparisonRun(Base):
    __tablename__ = "comparison_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), nullable=False, index=True)
    asso_enabled = Column(Boolean, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    peak_cpu = Column(Float, default=0.0)
    peak_memory = Column(Float, default=0.0)
    peak_latency = Column(Float, default=0.0)
    avg_latency = Column(Float, default=0.0)
    error_count = Column(Integer, default=0)
    total_requests = Column(Integer, default=0)
    breach_count = Column(Integer, default=0)

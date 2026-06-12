"""ASSO Configuration Module"""
import os

class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./asso.db")
    SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", "sqlite:///./asso.db")

    # Collector
    COLLECT_INTERVAL = float(os.getenv("COLLECT_INTERVAL", "1.5"))

    # Forecaster
    FORECAST_INTERVAL = float(os.getenv("FORECAST_INTERVAL", "3.0"))
    FORECAST_HORIZON = int(os.getenv("FORECAST_HORIZON", "60"))  # seconds ahead
    HISTORY_WINDOW = int(os.getenv("HISTORY_WINDOW", "120"))  # seconds of history

    # Thresholds
    CPU_WARNING = float(os.getenv("CPU_WARNING", "70"))
    CPU_CRITICAL = float(os.getenv("CPU_CRITICAL", "85"))
    MEMORY_WARNING = float(os.getenv("MEMORY_WARNING", "70"))
    MEMORY_CRITICAL = float(os.getenv("MEMORY_CRITICAL", "85"))
    LATENCY_WARNING = float(os.getenv("LATENCY_WARNING", "500"))
    LATENCY_CRITICAL = float(os.getenv("LATENCY_CRITICAL", "1000"))
    QUEUE_WARNING = int(os.getenv("QUEUE_WARNING", "100"))
    QUEUE_CRITICAL = int(os.getenv("QUEUE_CRITICAL", "200"))

    # Orchestrator risk thresholds
    RISK_LOW = float(os.getenv("RISK_LOW", "50"))
    RISK_MODERATE = float(os.getenv("RISK_MODERATE", "70"))
    RISK_HIGH = float(os.getenv("RISK_HIGH", "85"))
    RISK_CRITICAL = float(os.getenv("RISK_CRITICAL", "95"))

    # Rate limiting defaults
    DEFAULT_MAX_RPS = int(os.getenv("DEFAULT_MAX_RPS", "1000"))
    THROTTLED_RPS_MODERATE = int(os.getenv("THROTTLED_RPS_MODERATE", "200"))
    THROTTLED_RPS_HIGH = int(os.getenv("THROTTLED_RPS_HIGH", "50"))
    THROTTLED_RPS_CRITICAL = int(os.getenv("THROTTLED_RPS_CRITICAL", "10"))

    # Services
    SERVICES = [
        {
            "id": "flask-api",
            "name": "Flask REST API",
            "host": "127.0.0.1",
            "port": 6001,
            "service_type": "rest-api",
            "metrics_path": "/metrics",
            "health_path": "/health",
            "configure_path": "/configure",
        },
        {
            "id": "node-workload",
            "name": "Node.js Workload Service",
            "host": "127.0.0.1",
            "port": 6002,
            "service_type": "workload",
            "metrics_path": "/metrics",
            "health_path": "/health",
            "configure_path": "/configure",
        },
    ]

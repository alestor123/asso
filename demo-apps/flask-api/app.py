"""
ASSO Demo App — Flask REST API
A real Flask application that ASSO monitors and controls.
Features request tracking, configurable rate limiting, and work simulation endpoints.
"""
import time
import threading
import math
import os
import hashlib
from collections import deque
from flask import Flask, request, jsonify

app = Flask(__name__)

# ──────────────── Internal Metrics Tracking ────────────────

class MetricsTracker:
    """Tracks real request metrics for the /metrics endpoint"""

    def __init__(self):
        self.lock = threading.Lock()
        self.request_times = deque(maxlen=5000)  # timestamps of recent requests
        self.latencies = deque(maxlen=1000)       # recent latency measurements (ms)
        self.errors = deque(maxlen=1000)          # recent error flags
        self.active_connections = 0
        self.total_requests = 0
        self.queue = deque(maxlen=500)            # simulated work queue
        self.max_rps = int(os.getenv("MAX_RPS", "1000"))
        self.start_time = time.time()

    def record_request(self, latency_ms: float, is_error: bool = False):
        now = time.time()
        with self.lock:
            self.request_times.append(now)
            self.latencies.append(latency_ms)
            self.errors.append(1 if is_error else 0)
            self.total_requests += 1

    def get_request_rate(self) -> float:
        """Requests per second over the last 5 seconds"""
        now = time.time()
        cutoff = now - 5.0
        with self.lock:
            count = sum(1 for t in self.request_times if t > cutoff)
        return count / 5.0

    def get_avg_latency(self) -> float:
        with self.lock:
            if not self.latencies:
                return 0.0
            recent = list(self.latencies)[-50:]
            return sum(recent) / len(recent)

    def get_error_rate(self) -> float:
        with self.lock:
            if not self.errors:
                return 0.0
            recent = list(self.errors)[-100:]
            return sum(recent) / len(recent)

    def is_rate_limited(self) -> bool:
        return self.get_request_rate() > self.max_rps

    def configure(self, max_rps: int):
        with self.lock:
            self.max_rps = max_rps


metrics = MetricsTracker()


# ──────────────── Middleware ────────────────

@app.before_request
def before_request():
    request._start_time = time.time()
    metrics.active_connections += 1

@app.after_request
def after_request(response):
    latency_ms = (time.time() - getattr(request, '_start_time', time.time())) * 1000
    is_error = response.status_code >= 400
    metrics.record_request(latency_ms, is_error)
    metrics.active_connections = max(0, metrics.active_connections - 1)
    return response


# ──────────────── Endpoints ────────────────

@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "flask-api",
        "uptime": round(time.time() - metrics.start_time, 1),
        "total_requests": metrics.total_requests,
    })


@app.route("/metrics")
def get_metrics():
    """App-level metrics for ASSO telemetry collector"""
    return jsonify({
        "request_rate": round(metrics.get_request_rate(), 2),
        "latency_ms": round(metrics.get_avg_latency(), 2),
        "queue_length": len(metrics.queue),
        "error_rate": round(metrics.get_error_rate(), 4),
        "active_connections": metrics.active_connections,
        "total_requests": metrics.total_requests,
        "max_rps": metrics.max_rps,
    })


@app.route("/work", methods=["POST", "GET"])
def work():
    """
    Simulated work endpoint.
    Query params:
    - intensity: 1-10 (CPU work intensity)
    - duration_ms: target duration in milliseconds
    """
    # Rate limiting check
    if metrics.is_rate_limited():
        return jsonify({"error": "rate_limited", "max_rps": metrics.max_rps}), 429

    intensity = min(10, max(1, int(request.args.get("intensity", 3))))
    duration_ms = min(5000, max(10, int(request.args.get("duration_ms", 100))))

    # Add to queue
    metrics.queue.append(time.time())

    # Real CPU work — hashing and math operations
    start = time.time()
    target_end = start + (duration_ms / 1000.0)
    result = 0

    iterations = intensity * 1000
    while time.time() < target_end:
        for i in range(iterations):
            result += math.sin(i * 0.001) * math.cos(i * 0.002)
            if intensity > 5:
                hashlib.sha256(str(i).encode()).hexdigest()

    # Remove from queue
    try:
        metrics.queue.popleft()
    except IndexError:
        pass

    actual_duration = (time.time() - start) * 1000

    return jsonify({
        "status": "completed",
        "intensity": intensity,
        "target_ms": duration_ms,
        "actual_ms": round(actual_duration, 2),
        "result": round(result, 4),
    })


@app.route("/configure", methods=["POST"])
def configure():
    """ASSO orchestration endpoint — dynamically adjust rate limits"""
    data = request.get_json(silent=True) or {}
    max_rps = data.get("max_rps")
    action = data.get("action", "unknown")

    if max_rps is not None:
        metrics.configure(int(max_rps))

    return jsonify({
        "status": "configured",
        "action": action,
        "max_rps": metrics.max_rps,
    })


@app.route("/data", methods=["GET"])
def get_data():
    """Simple REST data endpoint"""
    items = [
        {"id": i, "name": f"Item {i}", "value": round(math.sin(i) * 100, 2)}
        for i in range(1, 11)
    ]
    return jsonify({"items": items, "count": len(items)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 6001))
    app.run(host="0.0.0.0", port=port, threaded=True)

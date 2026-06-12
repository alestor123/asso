"""ASSO Telemetry Collector — gathers REAL metrics from monitored services every 1-2 seconds"""
import asyncio
import time
import logging
from datetime import datetime
import psutil
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Service, Metric
from websocket_manager import ws_manager
from config import Config

logger = logging.getLogger("asso.collector")


class TelemetryCollector:
    """Collects real system + application metrics from monitored services"""

    def __init__(self):
        self.running = False
        self._task = None
        self._http_client = None
        self._process_cache: dict[str, psutil.Process] = {}

    async def start(self):
        """Start the collection loop"""
        self.running = True
        self._http_client = httpx.AsyncClient(timeout=2.0)
        self._task = asyncio.create_task(self._collect_loop())
        logger.info("Telemetry collector started (interval=%.1fs)", Config.COLLECT_INTERVAL)

    async def stop(self):
        """Stop the collection loop"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
        logger.info("Telemetry collector stopped")

    async def _collect_loop(self):
        """Main collection loop"""
        while self.running:
            try:
                start = time.monotonic()
                await self._collect_all_services()
                elapsed = time.monotonic() - start
                sleep_time = max(0.1, Config.COLLECT_INTERVAL - elapsed)
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Collection error: %s", e)
                await asyncio.sleep(1)

    async def _collect_all_services(self):
        """Collect metrics from all registered services"""
        async with async_session() as session:
            result = await session.execute(select(Service))
            services = result.scalars().all()

        for service in services:
            try:
                metric = await self._collect_service_metrics(service)
                if metric:
                    async with async_session() as session:
                        session.add(metric)
                        await session.commit()

                    # Broadcast to WebSocket clients
                    await ws_manager.broadcast("metric", {
                        "service_id": service.id,
                        "service_name": service.name,
                        "timestamp": metric.timestamp.isoformat(),
                        "cpu_percent": metric.cpu_percent,
                        "memory_mb": metric.memory_mb,
                        "memory_percent": metric.memory_percent,
                        "request_rate": metric.request_rate,
                        "latency_ms": metric.latency_ms,
                        "queue_length": metric.queue_length,
                        "error_rate": metric.error_rate,
                        "active_connections": metric.active_connections,
                    })

                    # Update service status
                    async with async_session() as session:
                        svc = await session.get(Service, service.id)
                        if svc:
                            svc.status = "healthy"
                            await session.commit()

            except Exception as e:
                logger.warning("Failed to collect from %s: %s", service.name, e)
                # Mark service as unhealthy
                async with async_session() as session:
                    svc = await session.get(Service, service.id)
                    if svc:
                        svc.status = "unhealthy"
                        await session.commit()

    async def _collect_service_metrics(self, service: Service) -> Metric | None:
        """Collect both system-level and app-level metrics for a service"""
        now = datetime.utcnow()

        # --- System metrics via psutil ---
        cpu_percent = 0.0
        memory_mb = 0.0
        memory_percent = 0.0

        if service.pid:
            try:
                proc = self._get_or_create_process(service.id, service.pid)
                cpu_percent = proc.cpu_percent(interval=0)
                mem_info = proc.memory_info()
                memory_mb = mem_info.rss / (1024 * 1024)
                memory_percent = proc.memory_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Try to find process by port
                pid = self._find_pid_by_port(service.port)
                if pid:
                    service.pid = pid
                    try:
                        proc = self._get_or_create_process(service.id, pid)
                        cpu_percent = proc.cpu_percent(interval=0)
                        mem_info = proc.memory_info()
                        memory_mb = mem_info.rss / (1024 * 1024)
                        memory_percent = proc.memory_percent()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        else:
            # Try to find the process by port
            pid = self._find_pid_by_port(service.port)
            if pid:
                service.pid = pid
                async with async_session() as session:
                    svc = await session.get(Service, service.id)
                    if svc:
                        svc.pid = pid
                        await session.commit()
                try:
                    proc = self._get_or_create_process(service.id, pid)
                    cpu_percent = proc.cpu_percent(interval=0)
                    mem_info = proc.memory_info()
                    memory_mb = mem_info.rss / (1024 * 1024)
                    memory_percent = proc.memory_percent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        # --- App-level metrics via HTTP ---
        request_rate = 0.0
        latency_ms = 0.0
        queue_length = 0
        error_rate = 0.0
        active_connections = 0

        try:
            url = f"http://{service.host}:{service.port}{service.metrics_path}"
            resp = await self._http_client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                request_rate = float(data.get("request_rate", 0))
                latency_ms = float(data.get("latency_ms", 0))
                queue_length = int(data.get("queue_length", 0))
                error_rate = float(data.get("error_rate", 0))
                active_connections = int(data.get("active_connections", 0))
        except Exception:
            pass  # App metrics unavailable; system metrics still valuable

        return Metric(
            timestamp=now,
            service_id=service.id,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            request_rate=request_rate,
            latency_ms=latency_ms,
            queue_length=queue_length,
            error_rate=error_rate,
            active_connections=active_connections,
        )

    def _get_or_create_process(self, service_id: str, pid: int) -> psutil.Process:
        """Cache psutil.Process objects to avoid repeated lookups"""
        cached = self._process_cache.get(service_id)
        if cached and cached.pid == pid and cached.is_running():
            return cached
        proc = psutil.Process(pid)
        self._process_cache[service_id] = proc
        return proc

    @staticmethod
    def _find_pid_by_port(port: int) -> int | None:
        """Find the PID of a process listening on the given port"""
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
                    return conn.pid
        except (psutil.AccessDenied, PermissionError):
            pass
        return None


# Global singleton
collector = TelemetryCollector()

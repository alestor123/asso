"""ASSO WebSocket Manager — broadcasts real-time updates to connected frontend clients"""
import json
import asyncio
from datetime import datetime
from fastapi import WebSocket
from typing import List


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages to all clients"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message_type: str, data: dict):
        """Broadcast a typed message to all connected clients"""
        payload = json.dumps({
            "type": message_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }, default=str)

        disconnected = []
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(payload)
                except Exception:
                    disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            async with self._lock:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

    async def send_personal(self, websocket: WebSocket, message_type: str, data: dict):
        """Send a message to a specific client"""
        payload = json.dumps({
            "type": message_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }, default=str)
        try:
            await websocket.send_text(payload)
        except Exception:
            await self.disconnect(websocket)


# Global singleton
ws_manager = ConnectionManager()

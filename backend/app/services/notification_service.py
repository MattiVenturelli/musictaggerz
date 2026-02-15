import asyncio
from typing import List, Optional
from fastapi import WebSocket

from app.utils.logger import log


class NotificationService:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the event loop for thread-safe broadcasting."""
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def _broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)

    def broadcast_sync(self, message: dict):
        """Thread-safe broadcast from sync code (worker threads)."""
        if not self.active_connections:
            return
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(message), self._loop)

    async def broadcast(self, message: dict):
        """Async broadcast from async code."""
        await self._broadcast(message)

    def send_album_update(self, album_id: int, status: str, **kwargs):
        """Send album status update (callable from sync code)."""
        self.broadcast_sync({
            "type": "album_update",
            "album_id": album_id,
            "status": status,
            **kwargs,
        })

    def send_progress(self, album_id: int, progress: float, message: str = ""):
        """Send progress update (callable from sync code)."""
        self.broadcast_sync({
            "type": "progress",
            "album_id": album_id,
            "progress": progress,
            "message": message,
        })

    def send_notification(self, level: str, message: str):
        """Send notification (callable from sync code)."""
        self.broadcast_sync({
            "type": "notification",
            "level": level,
            "message": message,
        })

    def send_scan_update(self, found: int, message: str = ""):
        """Send scan progress (callable from sync code)."""
        self.broadcast_sync({
            "type": "scan_update",
            "found": found,
            "message": message,
        })


notifications = NotificationService()

from typing import List
from fastapi import WebSocket
import json

from app.utils.logger import log


class NotificationService:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)

    async def send_album_update(self, album_id: int, status: str, **kwargs):
        await self.broadcast({
            "type": "album_update",
            "album_id": album_id,
            "status": status,
            **kwargs,
        })

    async def send_progress(self, album_id: int, progress: float, message: str = ""):
        await self.broadcast({
            "type": "progress",
            "album_id": album_id,
            "progress": progress,
            "message": message,
        })

    async def send_notification(self, level: str, message: str):
        await self.broadcast({
            "type": "notification",
            "level": level,
            "message": message,
        })


notifications = NotificationService()

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.notification_service import notifications

router = APIRouter()


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket):
    await notifications.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notifications.disconnect(websocket)

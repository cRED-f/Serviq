from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/events")
async def websocket_events(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "system",
            "event": "connected",
            "message": "Serviq WebSocket connected.",
        }
    )

    try:
        while True:
            payload = await websocket.receive_json()
            await websocket.send_json(
                {
                    "type": "echo",
                    "event": "backend_core_echo",
                    "payload": payload,
                }
            )
    except WebSocketDisconnect:
        logger.info("websocket_disconnected")

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

router = APIRouter(prefix="/inventario", tags=["inventario"])

class AdminConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def notify_admin(self, message: str, payload: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json({"message": message, "data": payload})
            except:
                pass

admin_ws_manager = AdminConnectionManager()

@router.websocket("/admin-ws")
async def inventario_admin_ws(websocket: WebSocket):
    await admin_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        admin_ws_manager.disconnect(websocket)

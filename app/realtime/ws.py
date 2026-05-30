import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import async_session_maker
from app.notifications.models import Alerta, AlertaTipo

router = APIRouter(tags=["ws"])

HEARTBEAT_SECONDS = 30


class ChannelManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(payload)
            except Exception:
                self.disconnect(connection)

    def has_connections(self) -> bool:
        return bool(self.active_connections)


totem_manager = ChannelManager()
vigilante_manager = ChannelManager()
admin_manager = ChannelManager()


async def _heartbeat_loop(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await websocket.send_json(
            {"tipo": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()}
        )


async def _send_pending_alerts(websocket: WebSocket) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Alerta)
            .where(Alerta.resolvido.is_(False))
            .order_by(Alerta.criado_em.asc())
        )
        alertas = result.scalars().all()

    for alerta in alertas:
        await websocket.send_json(
            {
                "tipo": "alerta",
                "mensagem": alerta.descricao,
                "nivel": "critico",
                "alerta_id": str(alerta.id),
            }
        )


async def broadcast_totem(payload: dict[str, Any]) -> None:
    await totem_manager.broadcast(payload)


async def broadcast_admin(payload: dict[str, Any]) -> None:
    await admin_manager.broadcast(payload)


async def broadcast_vigilante(
    payload: dict[str, Any],
    *,
    persist_if_offline: bool = False,
    alerta_tipo: AlertaTipo | None = None,
    descricao: str | None = None,
    session_id: uuid.UUID | None = None,
    livro_id: uuid.UUID | None = None,
) -> None:
    if vigilante_manager.has_connections():
        await vigilante_manager.broadcast(payload)
        return

    if persist_if_offline:
        if alerta_tipo is None:
            alerta_tipo = AlertaTipo.livro_sumido
        if descricao is None:
            descricao = payload.get("mensagem", "Alerta pendente")
        async with async_session_maker() as session:
            alerta = Alerta(
                tipo=alerta_tipo,
                descricao=descricao,
                session_id=session_id,
                livro_id=livro_id,
            )
            session.add(alerta)
            await session.commit()


async def _ws_loop(
    websocket: WebSocket,
    manager: ChannelManager,
    on_connect: Callable[[WebSocket], Any] | None = None,
) -> None:
    await manager.connect(websocket)
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))
    try:
        if on_connect is not None:
            await on_connect(websocket)
        while True:
            await websocket.receive_text()
    finally:
        heartbeat_task.cancel()
        manager.disconnect(websocket)


@router.websocket("/ws/totem")
async def totem_ws(websocket: WebSocket) -> None:
    try:
        await _ws_loop(websocket, totem_manager)
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/vigilante")
async def vigilante_ws(websocket: WebSocket) -> None:
    async def _on_connect(ws: WebSocket) -> None:
        await _send_pending_alerts(ws)

    try:
        await _ws_loop(websocket, vigilante_manager, on_connect=_on_connect)
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/admin")
async def admin_ws(websocket: WebSocket) -> None:
    try:
        await _ws_loop(websocket, admin_manager)
    except WebSocketDisconnect:
        pass

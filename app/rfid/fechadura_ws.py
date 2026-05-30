from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
from datetime import datetime
from app.core.database import async_session_maker
from app.rfid.models import LogAcesso, FechaduraAcao, FechaduraOrigem
from app.notifications.models import Alerta, AlertaTipo
from pydantic import BaseModel

router = APIRouter(prefix="/fechadura", tags=["fechadura"])

class ConnectionManager:
    def __init__(self):
        self.active_connection: WebSocket | None = None
        self.porta_aberta: bool = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # Se o ESP32 se reconectar, sobrepõe a conexão anterior
        self.active_connection = websocket

    def disconnect(self, websocket: WebSocket):
        if self.active_connection == websocket:
            self.active_connection = None

    async def send_command(self, acao: str):
        if self.active_connection:
            await self.active_connection.send_json({"acao": acao})
            return True
        return False

manager = ConnectionManager()

async def safety_timeout_task():
    """Aguarda 30s. Se a porta continuar aberta, força o fechamento e gera alerta."""
    await asyncio.sleep(30)
    if manager.porta_aberta:
        # Tenta forçar fechamento via WebSocket
        await manager.send_command("fechar")
        
        # Gera alerta no banco para o Vigilante
        async with async_session_maker() as session:
            alerta = Alerta(
                tipo=AlertaTipo.timeout_fechadura,
                descricao="TIMEOUT DE SEGURANÇA: Fechadura ficou aberta por mais de 30s. Comando de fechamento forçado enviado."
            )
            session.add(alerta)
            await session.commit()

@router.websocket("/ws")
async def fechadura_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Recebe o ACK (confirmação) do ESP32. Ex: {"status": "aberto", "origem": "sistema"}
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            status = payload.get("status")
            origem_str = payload.get("origem", "sistema")
            
            # Converte a string de origem para o Enum
            origem_enum = FechaduraOrigem.sistema
            if origem_str == "admin":
                origem_enum = FechaduraOrigem.admin
            elif origem_str == "timeout":
                origem_enum = FechaduraOrigem.timeout

            async with async_session_maker() as session:
                if status == "aberto":
                    manager.porta_aberta = True
                    log = LogAcesso(
                        acao=FechaduraAcao.abrir,
                        origem=origem_enum,
                        timestamp=datetime.utcnow()
                    )
                    session.add(log)
                    await session.commit()
                    
                    # Dispara o timeout de 30s em background
                    asyncio.create_task(safety_timeout_task())
                    
                elif status == "fechado":
                    manager.porta_aberta = False
                    log = LogAcesso(
                        acao=FechaduraAcao.fechar,
                        origem=origem_enum,
                        timestamp=datetime.utcnow()
                    )
                    session.add(log)
                    await session.commit()
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


class ComandoFechadura(BaseModel):
    session_id: str | None = None

@router.post("/abrir", summary="Forçar Abertura da Fechadura", description="Dispara o sinal HTTP interno para o WebSocket do ESP32 abrir a fechadura fisicamente.")
async def abrir_fechadura(comando: ComandoFechadura):
    sucesso = await manager.send_command("abrir")
    if not sucesso:
        return {"status": "error", "detail": "Fechadura offline (ESP32 não conectado no WebSocket)"}
    return {"status": "success", "detail": "Comando abrir enviado"}

@router.post("/fechar", summary="Forçar Fechamento da Fechadura", description="Dispara o sinal HTTP interno para o WebSocket do ESP32 fechar a fechadura fisicamente.")
async def fechar_fechadura(comando: ComandoFechadura):
    sucesso = await manager.send_command("fechar")
    if not sucesso:
        return {"status": "error", "detail": "Fechadura offline (ESP32 não conectado no WebSocket)"}
    return {"status": "success", "detail": "Comando fechar enviado"}

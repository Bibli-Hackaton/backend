import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.auth.router import router as auth_router
from app.admin.router import router as admin_config_router
from app.rfid.router import router as rfid_router
from app.rfid.fechadura_ws import router as fechadura_router
from app.inventory.router import router as inventory_router
from app.sessions.router import router as sessions_router
from app.sessions.tasks import session_expiration_loop
from app.loans.router import router as loans_router
from app.routers.books import router as books_router
from app.routers.users import router as users_router
from app.notifications.router import router as alertas_router
from app.realtime.ws import router as realtime_router
from app.vigilante.router import router as vigilante_router

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "auth", "description": "Operações de Autenticação (Login e Validação de Tokens)."},
    {"name": "configuracoes", "description": "Parametros configuraveis pelo admin."},
    {"name": "usuarios", "description": "Gestão de usuários e permissões administrativas."},
    {"name": "rfid", "description": "Comunicação com Leitores RFID e Webhooks de Hardware."},
    {"name": "fechadura", "description": "Controle físico de acesso e WebSockets da Fechadura."},
    {"name": "inventario", "description": "Gestão de varredura de acervo em lote e relatórios de furos."},
    {"name": "livros", "description": "Cadastro de livros e log de auditoria (Rastreabilidade)."},
    {"name": "sessoes", "description": "Controle de entrada, permanencia e saida na biblioteca."},
    {"name": "emprestimos", "description": "Fluxo de emprestimo e historico de retiradas."},
    {"name": "alertas", "description": "Monitoramento de alertas e resolucao de incidentes."},
    {"name": "vigilante", "description": "Monitoramento em tempo real do estado da biblioteca."},
    {"name": "ws", "description": "WebSockets para canais em tempo real."},
]
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "auth", "description": "Operações de Autenticação (Login e Validação de Tokens)."},
    {"name": "configuracoes", "description": "Parametros configuraveis pelo admin."},
    {"name": "usuarios", "description": "Gestão de usuários e permissões administrativas."},
    {"name": "rfid", "description": "Comunicação com Leitores RFID e Webhooks de Hardware."},
    {"name": "fechadura", "description": "Controle físico de acesso e WebSockets da Fechadura."},
    {"name": "inventario", "description": "Gestão de varredura de acervo em lote e relatórios de furos."},
    {"name": "livros", "description": "Cadastro de livros e log de auditoria (Rastreabilidade)."},
    {"name": "sessoes", "description": "Controle de entrada, permanencia e saida na biblioteca."},
    {"name": "emprestimos", "description": "Fluxo de emprestimo e historico de retiradas."},
    {"name": "alertas", "description": "Monitoramento de alertas e resolucao de incidentes."},
    {"name": "vigilante", "description": "Monitoramento em tempo real do estado da biblioteca."},
    {"name": "ws", "description": "WebSockets para canais em tempo real."},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=tags_metadata,
)

app.include_router(auth_router)
app.include_router(admin_config_router)
app.include_router(users_router)
app.include_router(rfid_router)
app.include_router(fechadura_router)
app.include_router(inventory_router)
app.include_router(sessions_router)
app.include_router(books_router)
app.include_router(loans_router)
app.include_router(alertas_router)
app.include_router(realtime_router)
app.include_router(vigilante_router)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware de logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


# Handler global de exceções
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"},
    )


@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(session_expiration_loop())
    from app.admin.config_service import warm_config_cache
    await warm_config_cache()


@app.get("/")
async def root():
    return {"message": "Hello World!"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.auth.router import router as auth_router
from app.rfid.router import router as rfid_router
from app.rfid.fechadura_ws import router as fechadura_router
from app.inventory.router import router as inventory_router
from app.books.router import router as books_router

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "auth", "description": "Operações de Autenticação (Login e Validação de Tokens)."},
    {"name": "rfid", "description": "Comunicação com Leitores RFID e Webhooks de Hardware."},
    {"name": "fechadura", "description": "Controle físico de acesso e WebSockets da Fechadura."},
    {"name": "inventario", "description": "Gestão de varredura de acervo em lote e relatórios de furos."},
    {"name": "livros", "description": "Cadastro de livros e log de auditoria (Rastreabilidade)."},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=tags_metadata
)

app.include_router(auth_router)
app.include_router(rfid_router)
app.include_router(fechadura_router)
app.include_router(inventory_router)
app.include_router(books_router)

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

@app.get("/")
async def root():
    return {"message": "Bem vindo à API da Biblioteca Hackathon!"}

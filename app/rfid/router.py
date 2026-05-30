from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as redis
import json

from app.core.dependencies import get_db_session
from app.core.redis import get_redis
from app.rfid.schemas import RFIDReadRequest
from app.books.models import Book, MovimentacaoLivro, MovimentacaoTipo
from app.notifications.models import Alerta, AlertaTipo

router = APIRouter(prefix="/rfid", tags=["rfid"])

DEBOUNCE_SECONDS = 2
LATEST_EVENT_KEY = "rfid:latest_event"

@router.post("/leitura", summary="Processar Leitura Física do RFID", description="Endpoint chamado pelo leitor do totem (ESP32) contendo a tag lida. Implementa debounce de 2s e gera alerta se tag for desconhecida.")
async def process_rfid_read(
    payload: RFIDReadRequest, 
    db: AsyncSession = Depends(get_db_session),
    cache: redis.Redis = Depends(get_redis)
):
    # Debounce (evita leitura duplicada em menos de 2 segundos)
    debounce_key = f"rfid:debounce:{payload.rfid_tag}"
    if await cache.get(debounce_key):
        return {"status": "ignored", "reason": "debounce"}
    
    # Seta a chave de debounce por 2 segundos
    await cache.set(debounce_key, "1", ex=DEBOUNCE_SECONDS)

    # Busca o livro no banco pela tag
    query = select(Book).where(Book.rfid_tag == payload.rfid_tag)
    result = await db.execute(query)
    book = result.scalar_one_or_none()

    event_data = {
        "rfid_tag": payload.rfid_tag,
        "leitor_id": payload.leitor_id,
        "timestamp": payload.timestamp.isoformat()
    }

    if not book:
        # Tag desconhecida -> Gera alerta para vigilante
        alerta = Alerta(
            tipo=AlertaTipo.rfid_desconhecido,
            descricao=f"Leitura de tag RFID desconhecida no totem: {payload.rfid_tag} pelo leitor {payload.leitor_id}",
        )
        db.add(alerta)
        await db.commit()
        
        event_data["status"] = "unknown"
        await cache.set(LATEST_EVENT_KEY, json.dumps(event_data))
        return {"status": "alert_created", "detail": "Tag desconhecida"}

    # Tag conhecida -> Gera movimentação e atualiza evento
    movimentacao = MovimentacaoLivro(
        livro_id=book.id,
        tipo=MovimentacaoTipo.rfid_lido,
        detalhes={"leitor_id": payload.leitor_id}
    )
    db.add(movimentacao)
    await db.commit()

    event_data["status"] = "identified"
    event_data["book_id"] = str(book.id)
    event_data["book_estado"] = book.estado
    
    # Salva o evento internamente para a lógica de sessão consumir
    await cache.set(LATEST_EVENT_KEY, json.dumps(event_data))

    return {"status": "success", "detail": "Leitura processada"}

@router.post("/simular", summary="Simular Leitura RFID", description="Utilidade para ambiente de desenvolvimento. Funciona exatamente como /leitura, mas pode ser acionado via Swagger sem o hardware físico.")
async def simular_rfid(
    payload: RFIDReadRequest, 
    db: AsyncSession = Depends(get_db_session),
    cache: redis.Redis = Depends(get_redis)
):
    # Alias para ambiente de dev (faz o mesmo fluxo)
    return await process_rfid_read(payload, db, cache)

@router.get("/ultimo-evento", summary="Obter Último Evento RFID Lído", description="Consome o Redis para exibir rapidamente qual foi o evento mais recente captado pelo Totem. Útil para debug e WebSockets.")
async def get_ultimo_evento(cache: redis.Redis = Depends(get_redis)):
    data = await cache.get(LATEST_EVENT_KEY)
    if not data:
        return {"evento": None}
    return {"evento": json.loads(data)}

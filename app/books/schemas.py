from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
import uuid
from app.books.models import MovimentacaoTipo, BookEstado

class MovimentacaoLivroOut(BaseModel):
    id: uuid.UUID
    livro_id: uuid.UUID
    user_id: uuid.UUID | None
    tipo: MovimentacaoTipo
    detalhes: Dict[str, Any]
    timestamp: datetime

    class Config:
        from_attributes = True

class PaginatedMovimentacao(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[MovimentacaoLivroOut]

class UltimoVistoOut(BaseModel):
    livro_id: uuid.UUID
    ultimo_registro: MovimentacaoLivroOut | None

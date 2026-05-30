from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import uuid

from app.core.dependencies import get_db_session, get_current_user
from app.auth.models import User
from app.books.models import Book, MovimentacaoLivro
from app.books.schemas import PaginatedMovimentacao, UltimoVistoOut, MovimentacaoLivroOut

router = APIRouter(prefix="/livros", tags=["livros"])

@router.get("/{livro_id}/historico", response_model=PaginatedMovimentacao, summary="Histórico de Movimentações (Audit Log)", description="Retorna o histórico completo de movimentações de um livro de forma paginada. Excelente para auditoria de vida útil da obra.")
async def get_historico_livro(
    livro_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    livro = await db.get(Book, livro_id)
    if not livro:
        raise HTTPException(status_code=404, detail="Livro não encontrado")

    count_query = select(func.count()).select_from(MovimentacaoLivro).where(MovimentacaoLivro.livro_id == livro_id)
    total = await db.scalar(count_query)

    query = select(MovimentacaoLivro).where(MovimentacaoLivro.livro_id == livro_id).order_by(MovimentacaoLivro.timestamp.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    movimentacoes = result.scalars().all()

    return PaginatedMovimentacao(
        total=total,
        limit=limit,
        offset=offset,
        items=movimentacoes
    )

@router.get("/{livro_id}/ultimo-visto", response_model=UltimoVistoOut, summary="Último Registro Físico Visto", description="Faz uma busca otimizada trazendo o local ou totem exato onde a tag do livro apitou pela última vez.")
async def get_ultimo_visto(
    livro_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    livro = await db.get(Book, livro_id)
    if not livro:
        raise HTTPException(status_code=404, detail="Livro não encontrado")

    query = select(MovimentacaoLivro).where(MovimentacaoLivro.livro_id == livro_id).order_by(MovimentacaoLivro.timestamp.desc()).limit(1)
    result = await db.execute(query)
    ultima = result.scalar_one_or_none()

    return UltimoVistoOut(
        livro_id=livro_id,
        ultimo_registro=ultima
    )

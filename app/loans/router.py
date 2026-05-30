from datetime import date, datetime, timedelta, timezone
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.admin.config_service import get_config, get_required_int_config
from app.auth.models import User, UserRole
from app.books.models import Book, BookEstado, Loan, LoanEstado, MovimentacaoLivro, MovimentacaoTipo
from app.core.dependencies import get_current_user, get_db_session, require_role
from app.core.redis import get_redis
from app.inventory.ws import admin_ws_manager
from app.notifications.models import Alerta, AlertaTipo
from app.realtime.ws import broadcast_vigilante
from app.rfid.router import LATEST_EVENT_KEY
from app.rfid.fechadura_ws import manager as fechadura_manager
from app.sessions.models import Session, SessionEstado
from app.loans.schemas import LoanCreateRequest, LoanOut

router = APIRouter(prefix="/emprestimos", tags=["emprestimos"])

MAX_PRAZO_CONFIG_KEY = "dias_emprestimo_max"
RFID_EVENT_MAX_AGE_SEC = 60
RFID_RETURN_EVENT_MAX_AGE_SEC = 30
VISION_EVENT_MAX_AGE_SEC = 30
VISION_LATEST_EVENT_KEY = "vision:latest_event"


def _ensure_student(current_user: User) -> None:
    if current_user.role != UserRole.aluno:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas alunos podem solicitar emprestimo",
        )


def _parse_event_timestamp(timestamp_str: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(timestamp_str)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


async def _get_latest_event(cache: redis.Redis, key: str) -> dict | None:
    raw_event = await cache.get(key)
    if not raw_event:
        return None
    try:
        return json.loads(raw_event)
    except json.JSONDecodeError:
        return None


def _is_recent(event_time: datetime, max_age_sec: int) -> bool:
    now = datetime.now(timezone.utc)
    return (now - event_time).total_seconds() <= max_age_sec


async def _notify_vigilante_bloqueio(
    db: AsyncSession,
    sessao: Session,
    loan: Loan,
    motivo: str,
    codigo: str,
) -> None:
    alerta = Alerta(
        tipo=AlertaTipo.livro_sumido,
        session_id=sessao.id,
        livro_id=loan.book_id,
        descricao=motivo,
    )
    db.add(alerta)
    await db.commit()
    await broadcast_vigilante(
        {
            "tipo": "devolucao_bloqueada",
            "codigo": codigo,
            "loan_id": str(loan.id),
            "book_id": str(loan.book_id),
            "session_id": str(sessao.id),
            "mensagem": motivo,
        }
    )


@router.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
async def registrar_emprestimo(
    payload: LoanCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    cache: redis.Redis = Depends(get_redis),
    config: dict[str, str] = Depends(get_config),
):
    _ensure_student(current_user)

    session_query = select(Session).where(
        and_(
            Session.user_id == current_user.id,
            Session.estado == SessionEstado.ativa,
        )
    )
    session_result = await db.execute(session_query)
    sessao = session_result.scalar_one_or_none()
    if not sessao:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao ativa nao encontrada",
        )

    loan_query = select(Loan).where(
        and_(Loan.user_id == current_user.id, Loan.estado == LoanEstado.ativo)
    )
    loan_result = await db.execute(loan_query)
    if loan_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Devolva o livro atual antes de pegar outro",
        )

    book = await db.get(Book, payload.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Livro nao encontrado")

    if book.estado != BookEstado.disponivel:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Livro ja emprestado",
        )

    max_prazo = get_required_int_config(config, MAX_PRAZO_CONFIG_KEY)
    if payload.dias_prazo > max_prazo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prazo excede o maximo permitido",
        )

    raw_event = await cache.get(LATEST_EVENT_KEY)
    if not raw_event:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passe o livro no leitor RFID primeiro",
        )

    try:
        event_data = json.loads(raw_event)
    except json.JSONDecodeError:
        event_data = None

    if not event_data or event_data.get("status") != "identified":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passe o livro no leitor RFID primeiro",
        )

    if event_data.get("book_id") != str(book.id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passe o livro no leitor RFID primeiro",
        )

    timestamp_str = event_data.get("timestamp")
    event_time = _parse_event_timestamp(timestamp_str) if timestamp_str else None
    if not event_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passe o livro no leitor RFID primeiro",
        )

    now = datetime.now(timezone.utc)
    if (now - event_time).total_seconds() > RFID_EVENT_MAX_AGE_SEC:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passe o livro no leitor RFID primeiro",
        )

    data_prevista = date.fromordinal(
        (now.date() + timedelta(days=payload.dias_prazo)).toordinal()
    )
    emprestimo = Loan(
        user_id=current_user.id,
        book_id=book.id,
        session_id=sessao.id,
        dias_prazo=payload.dias_prazo,
        data_emprestimo=now,
        data_prevista_devolucao=data_prevista,
        estado=LoanEstado.ativo,
    )
    book.estado = BookEstado.emprestado
    sessao.livro_retirado_id = book.id

    movimentacao = MovimentacaoLivro(
        livro_id=book.id,
        user_id=current_user.id,
        tipo=MovimentacaoTipo.emprestimo,
        detalhes={"session_id": str(sessao.id)},
    )

    db.add(emprestimo)
    db.add(movimentacao)
    await db.commit()
    await db.refresh(emprestimo)

    await admin_ws_manager.notify_admin(
        "emprestimo_registrado",
        {
            "loan_id": str(emprestimo.id),
            "book_id": str(book.id),
            "user_id": str(current_user.id),
            "session_id": str(sessao.id),
        },
    )

    return emprestimo


@router.get("/meus", response_model=list[LoanOut])
async def listar_meus_emprestimos(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Loan)
        .where(Loan.user_id == current_user.id)
        .order_by(Loan.data_emprestimo.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("", response_model=list[LoanOut])
async def listar_emprestimos(
    estado: LoanEstado | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    book_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
):
    del current_user

    query = select(Loan)
    if estado is not None:
        query = query.where(Loan.estado == estado)
    if user_id is not None:
        query = query.where(Loan.user_id == user_id)
    if book_id is not None:
        query = query.where(Loan.book_id == book_id)

    result = await db.execute(query.order_by(Loan.data_emprestimo.desc()))
    return result.scalars().all()


@router.post("/{loan_id}/devolver", response_model=LoanOut)
async def devolver_emprestimo(
    loan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    cache: redis.Redis = Depends(get_redis),
):
    loan = await db.get(Loan, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Emprestimo nao encontrado")

    if loan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Emprestimo nao pertence ao usuario",
        )

    if loan.estado == LoanEstado.devolvido:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Emprestimo ja devolvido",
        )

    session_query = (
        select(Session)
        .where(and_(Session.user_id == current_user.id, Session.estado == SessionEstado.ativa))
        .order_by(Session.iniciada_em.desc())
        .limit(1)
    )
    session_result = await db.execute(session_query)
    sessao = session_result.scalar_one_or_none()
    if not sessao:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao ativa nao encontrada",
        )

    rfid_event = await _get_latest_event(cache, LATEST_EVENT_KEY)
    if not rfid_event or rfid_event.get("status") != "identified":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Livro nao bipado via RFID na sessao atual",
        )

    if rfid_event.get("book_id") != str(loan.book_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Livro nao bipado via RFID na sessao atual",
        )

    rfid_timestamp = rfid_event.get("timestamp")
    rfid_time = _parse_event_timestamp(rfid_timestamp) if rfid_timestamp else None
    if not rfid_time or not _is_recent(rfid_time, RFID_RETURN_EVENT_MAX_AGE_SEC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Livro nao bipado via RFID na sessao atual",
        )

    if sessao.iniciada_em and rfid_time < sessao.iniciada_em:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Livro nao bipado via RFID na sessao atual",
        )

    vision_event = await _get_latest_event(cache, VISION_LATEST_EVENT_KEY)
    if not vision_event or vision_event.get("book_id") != str(loan.book_id):
        await _notify_vigilante_bloqueio(
            db,
            sessao,
            loan,
            "Devolucao bloqueada: webcam nao confirmou o livro na mesinha.",
            "webcam_ausente",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Webcam nao confirmou o livro na mesinha",
        )

    vision_timestamp = vision_event.get("timestamp")
    vision_time = _parse_event_timestamp(vision_timestamp) if vision_timestamp else None
    if not vision_time or not _is_recent(vision_time, VISION_EVENT_MAX_AGE_SEC):
        await _notify_vigilante_bloqueio(
            db,
            sessao,
            loan,
            "Devolucao bloqueada: webcam nao confirmou o livro na mesinha.",
            "webcam_timeout",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Webcam nao confirmou o livro na mesinha",
        )

    book = await db.get(Book, loan.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Livro nao encontrado")

    now = datetime.now(timezone.utc)
    loan.estado = LoanEstado.devolvido
    loan.data_devolucao = now
    book.estado = BookEstado.disponivel

    movimentacao = MovimentacaoLivro(
        livro_id=book.id,
        user_id=current_user.id,
        tipo=MovimentacaoTipo.devolucao,
        detalhes={"loan_id": str(loan.id), "session_id": str(sessao.id)},
    )
    db.add(movimentacao)

    sessao.estado = SessionEstado.encerrada
    sessao.encerrada_em = now
    sessao.livro_retirado_id = None

    await db.commit()
    await db.refresh(loan)
    await fechadura_manager.send_command("fechar")
    return loan


@router.get("/atrasados", response_model=list[LoanOut])
async def listar_emprestimos_atrasados(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
):
    today = datetime.now(timezone.utc).date()
    query = select(Loan).where(
        or_(
            Loan.estado == LoanEstado.atrasado,
            and_(Loan.estado == LoanEstado.ativo, Loan.data_prevista_devolucao < today),
        )
    )
    result = await db.execute(query.order_by(Loan.data_prevista_devolucao.asc()))
    return result.scalars().all()

from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.config_service import get_config, get_required_int_config
from app.auth.models import User, UserRole
from app.books.models import Loan, LoanEstado
from app.core.dependencies import get_current_user, get_db_session, require_role
from app.rfid.fechadura_ws import manager as fechadura_manager
from app.sessions.models import Session, SessionEstado
from app.sessions.schemas import (
    SessionCreateRequest,
    SessionEncerrarRequest,
    SessionOut,
    SessionRejectRequest,
)

router = APIRouter(prefix="/sessoes", tags=["sessoes"])

COOLDOWN_CONFIG_KEY = "cooldown_reentrada_min"
TEMPO_SESSAO_MAX_CONFIG_KEY = "tempo_sessao_max_min"
APPROVAL_TIMEOUT_MIN = 5


def _ensure_student(current_user: User) -> None:
    if current_user.role != UserRole.aluno:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas alunos podem solicitar sessao",
        )


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def criar_sessao(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    config: dict[str, str] = Depends(get_config),
):
    _ensure_student(current_user)

    active_query = select(Session).where(
        and_(
            Session.user_id == current_user.id,
            Session.estado.in_(
                [SessionEstado.aguardando_aprovacao, SessionEstado.ativa]
            ),
        )
    )
    active_result = await db.execute(active_query)
    if active_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aluno ja possui sessao ativa",
        )

    loan_query = select(Loan).where(
        and_(Loan.user_id == current_user.id, Loan.estado == LoanEstado.ativo)
    )
    loan_result = await db.execute(loan_query)
    if loan_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Devolucao de livro e fluxo separado",
        )

    tempo_sessao_max = get_required_int_config(config, TEMPO_SESSAO_MAX_CONFIG_KEY)
    if payload.tempo_estimado_min > tempo_sessao_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tempo estimado excede o maximo permitido",
        )

    cooldown_min = get_required_int_config(config, COOLDOWN_CONFIG_KEY)
    last_end_query = (
        select(Session.encerrada_em)
        .where(
            and_(
                Session.user_id == current_user.id,
                Session.encerrada_em.is_not(None),
            )
        )
        .order_by(Session.encerrada_em.desc())
        .limit(1)
    )
    last_end_result = await db.execute(last_end_query)
    last_encerrada = last_end_result.scalar_one_or_none()

    if last_encerrada:
        now = datetime.now(timezone.utc)
        if now - last_encerrada < timedelta(minutes=cooldown_min):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Aguarde antes de criar nova sessao",
            )

    sessao = Session(
        user_id=current_user.id,
        estado=SessionEstado.aguardando_aprovacao,
        tempo_estimado_min=payload.tempo_estimado_min,
    )
    db.add(sessao)
    await db.commit()
    await db.refresh(sessao)
    return sessao


@router.post("/{sessao_id}/aprovar", response_model=SessionOut)
async def aprovar_sessao(
    sessao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
):
    sessao = await db.get(Session, sessao_id)
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")

    if sessao.estado != SessionEstado.aguardando_aprovacao:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao nao esta aguardando aprovacao",
        )

    now = datetime.now(timezone.utc)
    if sessao.criado_em and now >= sessao.criado_em + timedelta(minutes=APPROVAL_TIMEOUT_MIN):
        sessao.estado = SessionEstado.expirada
        sessao.expira_em = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao expirou sem aprovacao",
        )

    sessao.estado = SessionEstado.ativa
    sessao.iniciada_em = now
    sessao.expira_em = now + timedelta(minutes=sessao.tempo_estimado_min)
    sessao.aprovada_por = current_user.id

    await db.commit()
    await db.refresh(sessao)
    await fechadura_manager.send_command("abrir")
    return sessao


@router.post("/{sessao_id}/rejeitar", response_model=SessionOut)
async def rejeitar_sessao(
    sessao_id: uuid.UUID,
    payload: SessionRejectRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
):
    sessao = await db.get(Session, sessao_id)
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")

    if sessao.estado != SessionEstado.aguardando_aprovacao:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao nao esta aguardando aprovacao",
        )

    sessao.estado = SessionEstado.rejeitada
    sessao.motivo_rejeicao = payload.motivo_rejeicao
    sessao.aprovada_por = current_user.id

    await db.commit()
    await db.refresh(sessao)
    return sessao


@router.post("/{sessao_id}/solicitar-saida", response_model=SessionOut)
async def solicitar_saida(
    sessao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    _ensure_student(current_user)

    sessao = await db.get(Session, sessao_id)
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")

    if sessao.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sessao invalida")

    if sessao.estado != SessionEstado.ativa:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao nao esta ativa",
        )

    if sessao.livro_retirado_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao possui livro retirado",
        )

    return sessao


@router.post("/{sessao_id}/encerrar", response_model=SessionOut)
async def encerrar_sessao(
    sessao_id: uuid.UUID,
    payload: SessionEncerrarRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
):
    sessao = await db.get(Session, sessao_id)
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")

    if sessao.estado == SessionEstado.encerrada:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao ja encerrada",
        )

    if sessao.estado in [SessionEstado.aguardando_aprovacao, SessionEstado.rejeitada]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sessao nao esta ativa",
        )

    sessao.estado = SessionEstado.encerrada
    sessao.encerrada_em = datetime.now(timezone.utc)
    sessao.livro_retirado_id = payload.livro_retirado_id
    sessao.aprovada_por = current_user.id

    await db.commit()
    await db.refresh(sessao)
    await fechadura_manager.send_command("fechar")
    return sessao


@router.get("/ativa", response_model=SessionOut)
async def obter_sessao_ativa(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Session)
        .where(
            and_(
                Session.user_id == current_user.id,
                Session.estado == SessionEstado.ativa,
            )
        )
        .order_by(Session.iniciada_em.desc())
        .limit(1)
    )
    result = await db.execute(query)
    sessao = result.scalar_one_or_none()
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessao ativa nao encontrada")
    return sessao


@router.get("", response_model=list[SessionOut])
async def listar_sessoes(
    estado: SessionEstado | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    data_inicio: datetime | None = Query(default=None),
    data_fim: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
):
    del current_user

    query = select(Session)

    if estado is not None:
        query = query.where(Session.estado == estado)
    if user_id is not None:
        query = query.where(Session.user_id == user_id)
    if data_inicio is not None:
        query = query.where(Session.criado_em >= data_inicio)
    if data_fim is not None:
        query = query.where(Session.criado_em <= data_fim)

    result = await db.execute(query.order_by(Session.criado_em.desc()))
    return result.scalars().all()

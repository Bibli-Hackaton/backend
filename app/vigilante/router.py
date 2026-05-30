from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.books.models import Loan, LoanEstado
from app.core.dependencies import get_db_session, require_role
from app.notifications.models import Alerta, AlertaTipo
from app.sessions.models import Session, SessionEstado
from app.sessions.schemas import SessionOut
from app.vigilante.schemas import (
    AlertaOut,
    AlertaResolverRequest,
    LoanOverdueOut,
    LoanOverdueUserOut,
)

router = APIRouter(prefix="/vigilante", tags=["vigilante"])

ALERT_TYPES = (
    AlertaTipo.sessao_expirada,
    AlertaTipo.rfid_desconhecido,
    AlertaTipo.webcam_offline,
    AlertaTipo.saida_sem_aprovacao,
    AlertaTipo.livro_sumido,
)


@router.get("/sessoes-ativas", response_model=list[SessionOut])
async def listar_sessoes_ativas(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
) -> list[SessionOut]:
    query = (
        select(Session)
        .where(Session.estado.in_([SessionEstado.aguardando_aprovacao, SessionEstado.ativa]))
        .order_by(Session.criado_em.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/fila", response_model=list[SessionOut])
async def listar_fila(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
) -> list[SessionOut]:
    now = datetime.now(timezone.utc)
    query = (
        select(Session)
        .where(
            or_(
                Session.estado == SessionEstado.aguardando_aprovacao,
                and_(Session.estado == SessionEstado.ativa, Session.expira_em <= now),
            )
        )
        .order_by(func.coalesce(Session.expira_em, Session.criado_em).asc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/alertas", response_model=list[AlertaOut])
async def listar_alertas(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
) -> list[AlertaOut]:
    query = (
        select(Alerta)
        .where(and_(Alerta.resolvido.is_(False), Alerta.tipo.in_(ALERT_TYPES)))
        .order_by(Alerta.criado_em.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/alertas/{alerta_id}/resolver", response_model=AlertaOut)
async def resolver_alerta(
    alerta_id: uuid.UUID,
    payload: AlertaResolverRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
) -> AlertaOut:
    alerta = await db.get(Alerta, alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta nao encontrado")

    if alerta.resolvido:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Alerta ja resolvido",
        )

    alerta.resolvido = True
    alerta.resolvido_em = datetime.now(timezone.utc)
    alerta.resolvido_por = current_user.id
    alerta.observacao = payload.observacao

    await db.commit()
    await db.refresh(alerta)
    return alerta


@router.get("/emprestimos-atrasados", response_model=list[LoanOverdueOut])
async def listar_emprestimos_atrasados(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
) -> list[LoanOverdueOut]:
    today = datetime.now(timezone.utc).date()
    query = (
        select(Loan, User)
        .join(User, User.id == Loan.user_id)
        .where(
            and_(
                Loan.estado.in_([LoanEstado.ativo, LoanEstado.atrasado]),
                Loan.data_prevista_devolucao < today,
            )
        )
        .order_by(Loan.data_prevista_devolucao.asc())
    )
    result = await db.execute(query)

    response: list[LoanOverdueOut] = []
    for loan, user in result.all():
        response.append(
            LoanOverdueOut(
                id=loan.id,
                user_id=loan.user_id,
                book_id=loan.book_id,
                session_id=loan.session_id,
                dias_prazo=loan.dias_prazo,
                estado=loan.estado,
                data_emprestimo=loan.data_emprestimo,
                data_prevista_devolucao=loan.data_prevista_devolucao,
                data_devolucao=loan.data_devolucao,
                aluno=LoanOverdueUserOut(
                    id=user.id,
                    nome=user.nome,
                    email=user.email,
                ),
            )
        )

    return response

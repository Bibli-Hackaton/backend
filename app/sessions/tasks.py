import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.notifications.models import Alerta, AlertaTipo
from app.realtime.ws import broadcast_vigilante
from app.sessions.models import Session, SessionEstado

logger = logging.getLogger(__name__)

EXPIRATION_CHECK_INTERVAL_SEC = 60
APPROVAL_TIMEOUT_MIN = 5


async def _alerta_pendente(
    session: AsyncSession,
    tipo: AlertaTipo,
    *,
    session_id: uuid.UUID | None = None,
    livro_id: uuid.UUID | None = None,
) -> bool:
    query = select(Alerta.id).where(
        Alerta.tipo == tipo,
        Alerta.resolvido.is_(False),
    )
    if session_id is not None:
        query = query.where(Alerta.session_id == session_id)
    if livro_id is not None:
        query = query.where(Alerta.livro_id == livro_id)
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none() is not None


async def expire_sessions_once() -> None:
    now = datetime.now(timezone.utc)
    updated = False
    created_alerts: list[Alerta] = []

    async with async_session_maker() as session:
        active_query = select(Session).where(Session.estado == SessionEstado.ativa)
        active_result = await session.execute(active_query)
        active_sessions = active_result.scalars().all()

        for sessao in active_sessions:
            if sessao.iniciada_em is None:
                continue
            tempo_min = max(sessao.tempo_estimado_min, 1)
            limite = sessao.iniciada_em + timedelta(minutes=tempo_min)
            limite_duplo = sessao.iniciada_em + timedelta(minutes=tempo_min * 2)

            if now >= limite:
                sessao.estado = SessionEstado.expirada
                sessao.expira_em = now
                if not await _alerta_pendente(
                    session,
                    AlertaTipo.sessao_expirada,
                    session_id=sessao.id,
                ):
                    alerta = Alerta(
                        tipo=AlertaTipo.sessao_expirada,
                        session_id=sessao.id,
                        descricao="Sessao expirada por tempo estimado excedido.",
                    )
                    session.add(alerta)
                    created_alerts.append(alerta)
                updated = True

            if now >= limite_duplo:
                if not await _alerta_pendente(
                    session,
                    AlertaTipo.saida_sem_aprovacao,
                    session_id=sessao.id,
                ):
                    alerta = Alerta(
                        tipo=AlertaTipo.saida_sem_aprovacao,
                        session_id=sessao.id,
                        descricao="Sessao excedeu duas vezes o tempo estimado.",
                    )
                    session.add(alerta)
                    created_alerts.append(alerta)
                    updated = True

        pending_query = select(Session).where(Session.estado == SessionEstado.aguardando_aprovacao)
        pending_result = await session.execute(pending_query)
        pending_sessions = pending_result.scalars().all()

        for sessao in pending_sessions:
            if sessao.criado_em is None:
                continue
            if now >= sessao.criado_em + timedelta(minutes=APPROVAL_TIMEOUT_MIN):
                sessao.estado = SessionEstado.expirada
                sessao.expira_em = now
                updated = True

        if updated:
            await session.commit()

    for alerta in created_alerts:
        await broadcast_vigilante(
            {
                "tipo": "alerta",
                "mensagem": alerta.descricao,
                "nivel": "critico",
                "alerta_id": str(alerta.id),
            }
        )


async def session_expiration_loop() -> None:
    while True:
        try:
            await expire_sessions_once()
        except Exception as exc:
            logger.warning("Falha ao processar expiracao de sessoes: %s", exc)
        await asyncio.sleep(EXPIRATION_CHECK_INTERVAL_SEC)

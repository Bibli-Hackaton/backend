from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.core.dependencies import get_db_session, require_role
from app.notifications.models import Alerta, AlertaTipo
from app.realtime.ws import broadcast_vigilante
from app.vigilante.schemas import AlertaOut, AlertaResolverRequest


router = APIRouter(prefix="/alertas", tags=["alertas"])


class WebcamRemocaoRequest(BaseModel):
    livro_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    descricao: str | None = None


@router.get("", response_model=list[AlertaOut])
async def listar_alertas(
    resolvido: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
) -> list[AlertaOut]:
    query = select(Alerta)
    if resolvido is not None:
        query = query.where(Alerta.resolvido.is_(resolvido))
    result = await db.execute(query.order_by(Alerta.criado_em.desc()))
    return result.scalars().all()


@router.post("/{alerta_id}/resolver", response_model=AlertaOut)
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


@router.post("/webcam-remocao", response_model=AlertaOut, status_code=status.HTTP_201_CREATED)
async def registrar_remocao_webcam(
    payload: WebcamRemocaoRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(UserRole.vigilante, UserRole.admin)),
) -> AlertaOut:
    alerta = Alerta(
        tipo=AlertaTipo.livro_sumido,
        session_id=payload.session_id,
        livro_id=payload.livro_id,
        descricao=payload.descricao
        or "Webcam detectou remocao de livro sem RFID bipado.",
    )

    db.add(alerta)
    await db.commit()
    await db.refresh(alerta)

    await broadcast_vigilante(
        {
            "tipo": "alerta",
            "mensagem": alerta.descricao,
            "nivel": "critico",
            "alerta_id": str(alerta.id),
        }
    )

    return alerta

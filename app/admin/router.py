from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.admin.config_service import (
    CONFIG_CACHE_KEY,
    get_config_cache,
    validate_config_value,
)
from app.admin.models import Config
from app.admin.schemas import ConfigOut, ConfigUpdate
from app.auth.models import User, UserRole
from app.core.dependencies import get_db_session, require_role
from app.core.redis import get_redis

router = APIRouter(prefix="/config", tags=["configuracoes"])


@router.get("", response_model=list[ConfigOut])
async def listar_configuracoes(
    db: AsyncSession = Depends(get_db_session),
    cache: redis.Redis = Depends(get_redis),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    del current_user
    return await get_config_cache(db, cache)


@router.patch("/{chave}", response_model=ConfigOut)
async def atualizar_configuracao(
    chave: str,
    payload: ConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
    cache: redis.Redis = Depends(get_redis),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    config_result = await db.execute(select(Config).where(Config.chave == chave))
    config = config_result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuracao nao encontrada",
        )

    config.valor = validate_config_value(chave, payload.valor)
    config.atualizado_por = current_user.id

    await db.commit()
    await db.refresh(config)
    await cache.delete(CONFIG_CACHE_KEY)

    return config

from __future__ import annotations

import json
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.admin.models import Config
from app.core.database import async_session_maker
from app.core.dependencies import get_db_session
from app.core.redis import get_redis, redis_client

CONFIG_CACHE_KEY = "config:all"
CONFIG_CACHE_TTL_SEC = 300

CONFIG_SPECS: dict[str, dict[str, Any]] = {
    "tempo_sessao_max_min": {"type": int, "min": 1},
    "dias_emprestimo_max": {"type": int, "min": 1},
    "cooldown_reentrada_min": {"type": int, "min": 1},
    "alertar_devolucao_dias_antes": {"type": int, "min": 0},
}


def _serialize_config(config: Config) -> dict[str, Any]:
    atualizado_em = config.atualizado_em.isoformat() if config.atualizado_em else None
    atualizado_por = str(config.atualizado_por) if config.atualizado_por else None
    return {
        "chave": config.chave,
        "valor": config.valor,
        "descricao": config.descricao,
        "atualizado_em": atualizado_em,
        "atualizado_por": atualizado_por,
    }


def _parse_int(chave: str, valor: str) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Valor invalido para configuracao '{chave}'. Esperado inteiro.",
        )


def _validate_min_value(chave: str, valor: int, min_value: int) -> None:
    if valor < min_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Valor invalido para configuracao '{chave}'. Minimo {min_value}.",
        )


def validate_config_value(chave: str, valor: str) -> str:
    spec = CONFIG_SPECS.get(chave)
    if not spec:
        return valor

    if spec.get("type") is int:
        parsed = _parse_int(chave, valor)
        min_value = spec.get("min")
        if min_value is not None:
            _validate_min_value(chave, parsed, min_value)
        return str(parsed)

    return valor


def get_required_int_config(configs: dict[str, str], chave: str) -> int:
    if chave not in configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuracao '{chave}' nao encontrada.",
        )
    return _parse_int(chave, configs[chave])


async def _fetch_configs(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(select(Config).order_by(Config.chave))
    configs = result.scalars().all()
    return [_serialize_config(config) for config in configs]


async def load_config_cache(db: AsyncSession, cache: redis.Redis) -> list[dict[str, Any]]:
    configs = await _fetch_configs(db)
    await cache.set(CONFIG_CACHE_KEY, json.dumps(configs), ex=CONFIG_CACHE_TTL_SEC)
    return configs


async def get_config_cache(
    db: AsyncSession, cache: redis.Redis
) -> list[dict[str, Any]]:
    cached = await cache.get(CONFIG_CACHE_KEY)
    if cached:
        return json.loads(cached)
    return await load_config_cache(db, cache)


async def get_config(
    db: AsyncSession = Depends(get_db_session),
    cache: redis.Redis = Depends(get_redis),
) -> dict[str, str]:
    configs = await get_config_cache(db, cache)
    return {item["chave"]: item["valor"] for item in configs}


async def warm_config_cache() -> None:
    async with async_session_maker() as session:
        await load_config_cache(session, redis_client)

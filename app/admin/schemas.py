from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConfigOut(BaseModel):
    chave: str
    valor: str
    descricao: str
    atualizado_em: datetime | None
    atualizado_por: UUID | None

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    valor: str = Field(min_length=1, max_length=2000)

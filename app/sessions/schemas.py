from datetime import datetime
import uuid
from pydantic import BaseModel, Field
from app.sessions.models import SessionEstado


class SessionCreateRequest(BaseModel):
    tempo_estimado_min: int = Field(ge=1)


class SessionRejectRequest(BaseModel):
    motivo_rejeicao: str = Field(min_length=1, max_length=500)


class SessionEncerrarRequest(BaseModel):
    livro_retirado_id: uuid.UUID | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    estado: SessionEstado
    tempo_estimado_min: int
    motivo_rejeicao: str | None
    iniciada_em: datetime | None
    encerrada_em: datetime | None
    expira_em: datetime | None
    livro_retirado_id: uuid.UUID | None
    aprovada_por: uuid.UUID | None
    criado_em: datetime

    class Config:
        from_attributes = True

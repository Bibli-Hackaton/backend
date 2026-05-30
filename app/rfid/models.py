import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class FechaduraAcao(str, enum.Enum):
    abrir = 'abrir'
    fechar = 'fechar'

class FechaduraOrigem(str, enum.Enum):
    sistema = 'sistema'
    admin = 'admin'
    timeout = 'timeout'

class LogAcesso(Base):
    __tablename__ = 'log_acesso'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('sessions.id'), nullable=True, index=True)
    acao: Mapped[FechaduraAcao] = mapped_column(Enum(FechaduraAcao, name='fechadura_acao'), nullable=False)
    origem: Mapped[FechaduraOrigem] = mapped_column(Enum(FechaduraOrigem, name='fechadura_origem'), nullable=False, default=FechaduraOrigem.sistema)
    confirmado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

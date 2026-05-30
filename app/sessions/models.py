import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class SessionEstado(str, enum.Enum):
    aguardando_aprovacao = 'aguardando_aprovacao'
    ativa = 'ativa'
    encerrada = 'encerrada'
    expirada = 'expirada'
    rejeitada = 'rejeitada'

class Session(Base):
    __tablename__ = 'sessions'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    estado: Mapped[SessionEstado] = mapped_column(Enum(SessionEstado, name='session_estado'), nullable=False, default=SessionEstado.aguardando_aprovacao, index=True)
    tempo_estimado_min: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo_rejeicao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    iniciada_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    encerrada_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expira_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    livro_retirado_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('books.id'), nullable=True)
    aprovada_por: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

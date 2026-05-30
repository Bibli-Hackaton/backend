import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class AlertaTipo(str, enum.Enum):
    saida_sem_aprovacao = 'saida_sem_aprovacao'
    livro_sumido = 'livro_sumido'
    rfid_desconhecido = 'rfid_desconhecido'
    webcam_offline = 'webcam_offline'
    sessao_expirada = 'sessao_expirada'

class Alerta(Base):
    __tablename__ = 'alertas'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo: Mapped[AlertaTipo] = mapped_column(Enum(AlertaTipo, name='alerta_tipo'), nullable=False, index=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('sessions.id'), nullable=True)
    livro_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('books.id'), nullable=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    resolvido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolvido_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolvido_por: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

import uuid
import enum
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class InventarioEstado(str, enum.Enum):
    em_andamento = 'em_andamento'
    finalizado = 'finalizado'
    cancelado = 'cancelado'

class SessaoInventario(Base):
    __tablename__ = 'sessao_inventario'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estado: Mapped[InventarioEstado] = mapped_column(Enum(InventarioEstado, name='inventario_estado'), nullable=False, default=InventarioEstado.em_andamento)
    iniciado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finalizado_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_cadastrado: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_lido: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_furos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    relatorio: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

class ItemInventario(Base):
    __tablename__ = 'item_inventario'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sessao_inventario.id', ondelete='CASCADE'), nullable=False, index=True)
    livro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('books.id'), nullable=False, index=True)
    rfid_tag: Mapped[str] = mapped_column(String, nullable=False)
    lido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

import uuid
import enum
from datetime import datetime, date
from typing import Optional, Dict, Any
from sqlalchemy import String, Boolean, DateTime, Date, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class BookEstado(str, enum.Enum):
    disponivel = 'disponivel'
    emprestado = 'emprestado'
    inventario = 'inventario'
    perdido = 'perdido'

class Book(Base):
    __tablename__ = 'books'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    autor: Mapped[str] = mapped_column(String, nullable=False)
    isbn: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    rfid_tag: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True, index=True)
    estado: Mapped[BookEstado] = mapped_column(Enum(BookEstado, name='book_estado'), nullable=False, default=BookEstado.disponivel, index=True)
    deletado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class LoanEstado(str, enum.Enum):
    ativo = 'ativo'
    devolvido = 'devolvido'
    atrasado = 'atrasado'

class Loan(Base):
    __tablename__ = 'loans'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('books.id'), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sessions.id'), nullable=False)
    dias_prazo: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[LoanEstado] = mapped_column(Enum(LoanEstado, name='loan_estado'), nullable=False, default=LoanEstado.ativo, index=True)
    data_emprestimo: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    data_prevista_devolucao: Mapped[date] = mapped_column(Date, nullable=False)
    data_devolucao: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class MovimentacaoTipo(str, enum.Enum):
    emprestimo = 'emprestimo'
    devolucao = 'devolucao'
    rfid_lido = 'rfid_lido'
    inventario = 'inventario'
    cadastro = 'cadastro'

class MovimentacaoLivro(Base):
    __tablename__ = 'movimentacao_livro'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    livro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('books.id'), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    tipo: Mapped[MovimentacaoTipo] = mapped_column(Enum(MovimentacaoTipo, name='movimentacao_tipo'), nullable=False, index=True)
    detalhes: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

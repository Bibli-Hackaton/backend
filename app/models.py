from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    aluno = "aluno"
    vigilante = "vigilante"
    admin = "admin"


class BookStatus(str, Enum):
    disponivel = "disponivel"
    emprestado = "emprestado"
    inventario = "inventario"
    perdido = "perdido"


class UserBase(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=255)


class UserCreate(UserBase):
    senha_hash: str = Field(min_length=8, max_length=255)
    role: UserRole


class UserUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    role: UserRole | None = None
    ativo: bool | None = None


class UserOut(UserBase):
    id: UUID
    role: UserRole
    ativo: bool
    criado_em: datetime


class LoanSummary(BaseModel):
    id: UUID
    livro_id: UUID
    usuario_id: UUID
    status: str
    criado_em: datetime
    devolvido_em: datetime | None


class BookBase(BaseModel):
    titulo: str = Field(min_length=1, max_length=255)
    autor: str = Field(min_length=1, max_length=255)
    isbn: str | None = Field(default=None, max_length=32)


class BookCreate(BookBase):
    rfid_tag: str | None = Field(default=None, max_length=64)


class BookUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=255)
    autor: str | None = Field(default=None, min_length=1, max_length=255)
    isbn: str | None = Field(default=None, max_length=32)


class BookOut(BookBase):
    id: UUID
    rfid_tag: str | None
    estado: BookStatus
    criado_em: datetime
    atualizado_em: datetime


class BookDetail(BaseModel):
    livro: BookOut
    emprestimo_ativo: LoanSummary | None


class BookRfidUpdate(BaseModel):
    rfid_tag: str = Field(min_length=1, max_length=64)

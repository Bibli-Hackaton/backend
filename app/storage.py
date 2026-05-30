from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict
from uuid import UUID, uuid4

from app.models import BookStatus, UserRole


@dataclass(slots=True)
class UserRecord:
    id: UUID
    nome: str
    email: str
    senha_hash: str
    role: UserRole
    ativo: bool
    criado_em: datetime


@dataclass(slots=True)
class BookRecord:
    id: UUID
    titulo: str
    autor: str
    isbn: str | None
    rfid_tag: str | None
    estado: BookStatus
    criado_em: datetime
    atualizado_em: datetime
    ativo: bool


@dataclass(slots=True)
class LoanRecord:
    id: UUID
    livro_id: UUID
    usuario_id: UUID
    status: str
    criado_em: datetime
    devolvido_em: datetime | None


USERS: Dict[UUID, UserRecord] = {}
BOOKS: Dict[UUID, BookRecord] = {}
LOANS: Dict[UUID, LoanRecord] = {}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_user_id() -> UUID:
    return uuid4()


def new_book_id() -> UUID:
    return uuid4()


def new_loan_id() -> UUID:
    return uuid4()

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import require_roles
from app.models import (
    BookCreate,
    BookDetail,
    BookOut,
    BookRfidUpdate,
    BookStatus,
    BookUpdate,
    LoanSummary,
    UserRole,
)
from app.storage import BOOKS, BookRecord, LOANS, new_book_id, now_utc

router = APIRouter(prefix="/livros", tags=["livros"])


def _book_to_out(book) -> BookOut:
    return BookOut(
        id=book.id,
        titulo=book.titulo,
        autor=book.autor,
        isbn=book.isbn,
        rfid_tag=book.rfid_tag,
        estado=book.estado,
        criado_em=book.criado_em,
        atualizado_em=book.atualizado_em,
    )


def _find_active_loan(book_id: UUID):
    for loan in LOANS.values():
        if loan.livro_id == book_id and loan.status == "ativo":
            return loan
    return None


def _rfid_in_use(tag: str, book_id: UUID | None = None):
    for book in BOOKS.values():
        if book.rfid_tag == tag and book.id != book_id:
            return book
    return None


@router.get("", response_model=list[BookOut])
async def list_books(
    estado: BookStatus | None = Query(default=None),
    autor: str | None = Query(default=None),
    titulo: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> list[BookOut]:
    books = [book for book in BOOKS.values() if book.ativo]

    if estado is not None:
        books = [book for book in books if book.estado == estado]

    if autor is not None:
        autor_norm = autor.strip().lower()
        books = [book for book in books if autor_norm in book.autor.lower()]

    if titulo is not None:
        titulo_norm = titulo.strip().lower()
        books = [book for book in books if titulo_norm in book.titulo.lower()]

    start = (page - 1) * size
    end = start + size

    return [_book_to_out(book) for book in books[start:end]]


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
async def create_book(
    payload: BookCreate,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> BookOut:
    if payload.rfid_tag:
        existing = _rfid_in_use(payload.rfid_tag)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tag ja vinculada ao livro {existing.titulo}",
            )

    book_id = new_book_id()
    created_at = now_utc()
    book = BookRecord(
        id=book_id,
        titulo=payload.titulo.strip(),
        autor=payload.autor.strip(),
        isbn=payload.isbn,
        rfid_tag=payload.rfid_tag,
        estado=BookStatus.disponivel,
        criado_em=created_at,
        atualizado_em=created_at,
        ativo=True,
    )
    BOOKS[book_id] = book

    return _book_to_out(book)


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(book_id: UUID) -> BookDetail:
    book = BOOKS.get(book_id)

    if book is None or not book.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro nao encontrado")

    loan = _find_active_loan(book_id)
    loan_summary = None

    if loan is not None:
        loan_summary = LoanSummary(
            id=loan.id,
            livro_id=loan.livro_id,
            usuario_id=loan.usuario_id,
            status=loan.status,
            criado_em=loan.criado_em,
            devolvido_em=loan.devolvido_em,
        )

    return BookDetail(livro=_book_to_out(book), emprestimo_ativo=loan_summary)


@router.patch("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: UUID,
    payload: BookUpdate,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> BookOut:
    book = BOOKS.get(book_id)

    if book is None or not book.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro nao encontrado")

    if payload.titulo is not None:
        book.titulo = payload.titulo.strip()

    if payload.autor is not None:
        book.autor = payload.autor.strip()

    if payload.isbn is not None:
        book.isbn = payload.isbn

    book.atualizado_em = now_utc()

    return _book_to_out(book)


@router.delete("/{book_id}", response_model=BookOut)
async def delete_book(
    book_id: UUID,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> BookOut:
    book = BOOKS.get(book_id)

    if book is None or not book.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro nao encontrado")

    if book.estado == BookStatus.emprestado:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Livro emprestado; devolva antes de excluir",
        )

    book.ativo = False
    book.atualizado_em = now_utc()

    return _book_to_out(book)


@router.post("/{book_id}/rfid", response_model=BookOut)
async def link_rfid(
    book_id: UUID,
    payload: BookRfidUpdate,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> BookOut:
    book = BOOKS.get(book_id)

    if book is None or not book.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro nao encontrado")

    existing = _rfid_in_use(payload.rfid_tag, book_id=book.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tag ja vinculada ao livro {existing.titulo}",
        )

    book.rfid_tag = payload.rfid_tag
    book.atualizado_em = now_utc()

    return _book_to_out(book)


@router.delete("/{book_id}/rfid", response_model=BookOut)
async def unlink_rfid(
    book_id: UUID,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> BookOut:
    book = BOOKS.get(book_id)

    if book is None or not book.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro nao encontrado")

    book.rfid_tag = None
    book.atualizado_em = now_utc()

    return _book_to_out(book)

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import require_roles
from app.models import LoanSummary, UserCreate, UserOut, UserRole, UserUpdate
from app.storage import LOANS, USERS, UserRecord, new_user_id, now_utc

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


def _active_admin_count(exclude_id: UUID | None = None) -> int:
    return sum(
        1
        for user in USERS.values()
        if user.ativo and user.role == UserRole.admin and user.id != exclude_id
    )


def _has_active_loan(user_id: UUID) -> bool:
    return any(
        loan.usuario_id == user_id and loan.status == "ativo" for loan in LOANS.values()
    )


def _ensure_admin_not_last(target_id: UUID, new_role: UserRole, new_active: bool) -> None:
    if new_role != UserRole.admin or not new_active:
        if _active_admin_count(exclude_id=target_id) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nao e permitido desativar o ultimo admin",
            )


def _ensure_student_deactivation_ok(user_id: UUID, role: UserRole, new_active: bool) -> None:
    if role == UserRole.aluno and not new_active and _has_active_loan(user_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aluno possui emprestimo ativo; devolva antes de desativar",
        )


def _user_to_out(user) -> UserOut:
    return UserOut(
        id=user.id,
        nome=user.nome,
        email=user.email,
        role=user.role,
        ativo=user.ativo,
        criado_em=user.criado_em,
    )


@router.get("", response_model=list[UserOut])
async def list_users(
    role: UserRole | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> list[UserOut]:
    users: Iterable = USERS.values()

    if role is not None:
        users = [user for user in users if user.role == role]

    start = (page - 1) * size
    end = start + size

    return [_user_to_out(user) for user in list(users)[start:end]]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> UserOut:
    normalized_email = payload.email.strip().lower()

    if any(user.email.lower() == normalized_email for user in USERS.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email ja cadastrado",
        )

    user_id = new_user_id()
    user = UserRecord(
        id=user_id,
        nome=payload.nome.strip(),
        email=normalized_email,
        senha_hash=payload.senha_hash,
        role=payload.role,
        ativo=True,
        criado_em=now_utc(),
    )
    USERS[user_id] = user

    return _user_to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> UserOut:
    user = USERS.get(user_id)

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    new_role = payload.role or user.role
    new_active = payload.ativo if payload.ativo is not None else user.ativo

    if user.role == UserRole.admin and (new_role != user.role or not new_active):
        _ensure_admin_not_last(user.id, new_role, new_active)

    _ensure_student_deactivation_ok(user.id, new_role, new_active)

    if payload.nome is not None:
        user.nome = payload.nome.strip()

    user.role = new_role
    user.ativo = new_active

    return _user_to_out(user)


@router.delete("/{user_id}", response_model=UserOut)
async def delete_user(
    user_id: UUID,
    _: str = Depends(require_roles(UserRole.admin.value)),
) -> UserOut:
    user = USERS.get(user_id)

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    if user.role == UserRole.admin:
        _ensure_admin_not_last(user.id, user.role, False)

    _ensure_student_deactivation_ok(user.id, user.role, False)

    user.ativo = False

    return _user_to_out(user)


@router.get("/{user_id}/emprestimos", response_model=list[LoanSummary])
async def list_user_loans(
    user_id: UUID,
    _: str = Depends(require_roles(UserRole.admin.value, UserRole.vigilante.value)),
) -> list[LoanSummary]:
    if user_id not in USERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    return [
        LoanSummary(
            id=loan.id,
            livro_id=loan.livro_id,
            usuario_id=loan.usuario_id,
            status=loan.status,
            criado_em=loan.criado_em,
            devolvido_em=loan.devolvido_em,
        )
        for loan in LOANS.values()
        if loan.usuario_id == user_id
    ]

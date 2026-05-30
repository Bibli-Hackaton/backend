from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.dependencies import get_db_session, get_current_user
from app.core.security import verify_password, create_access_token
from app.auth.models import User
from app.auth.schemas import LoginRequest, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token, summary="Login do Usuário", description="Recebe as credenciais do usuário e retorna um JWT (JSON Web Token) para acesso protegido às rotas.")
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    query = select(User).where(User.email == login_data.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut, summary="Obter dados do usuário logado", description="Retorna as informações do usuário atual (baseado no token enviado no Header Authorization).")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

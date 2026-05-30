import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.auth.models import UserRole

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: uuid.UUID
    nome: str
    email: EmailStr
    role: UserRole
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True

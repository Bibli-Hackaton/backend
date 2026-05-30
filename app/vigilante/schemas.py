from datetime import date, datetime
import uuid
from pydantic import BaseModel, Field
from app.notifications.models import AlertaTipo
from app.books.models import LoanEstado


class AlertaOut(BaseModel):
    id: uuid.UUID
    tipo: AlertaTipo
    session_id: uuid.UUID | None
    livro_id: uuid.UUID | None
    descricao: str
    resolvido: bool
    criado_em: datetime
    resolvido_em: datetime | None
    resolvido_por: uuid.UUID | None
    observacao: str | None

    class Config:
        from_attributes = True


class AlertaResolverRequest(BaseModel):
    observacao: str | None = Field(default=None, max_length=500)


class LoanOverdueUserOut(BaseModel):
    id: uuid.UUID
    nome: str
    email: str


class LoanOverdueOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    session_id: uuid.UUID
    dias_prazo: int
    estado: LoanEstado
    data_emprestimo: datetime
    data_prevista_devolucao: date
    data_devolucao: datetime | None
    aluno: LoanOverdueUserOut

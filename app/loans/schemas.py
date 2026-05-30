from datetime import date, datetime
import uuid
from pydantic import BaseModel, Field
from app.books.models import LoanEstado


class LoanCreateRequest(BaseModel):
    book_id: uuid.UUID
    dias_prazo: int = Field(ge=1)


class LoanOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    session_id: uuid.UUID
    dias_prazo: int
    data_emprestimo: datetime
    data_prevista_devolucao: date
    data_devolucao: datetime | None
    estado: LoanEstado

    class Config:
        from_attributes = True

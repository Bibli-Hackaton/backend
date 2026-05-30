from pydantic import BaseModel
from typing import List
from datetime import datetime
import uuid

class InventarioStartRequest(BaseModel):
    iniciado_por: uuid.UUID

class RegistroLeituraRequest(BaseModel):
    rfid_tags: List[str]

class FuroInfo(BaseModel):
    livro_id: str
    titulo: str
    rfid_tag: str
    ultimo_visto_em: str | None = None

class InventarioRelatorio(BaseModel):
    total_cadastrado: int
    total_lido: int
    presentes: int
    emprestados: int
    furos: List[FuroInfo]

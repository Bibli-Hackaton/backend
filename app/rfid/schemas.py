from datetime import datetime
from pydantic import BaseModel

class RFIDReadRequest(BaseModel):
    rfid_tag: str
    leitor_id: str
    timestamp: datetime

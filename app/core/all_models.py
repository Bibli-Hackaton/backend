# Centraliza a importação de todos os modelos para que o Alembic consiga encontrá-los
from app.core.database import Base

from app.auth.models import User
from app.books.models import Book, Loan, MovimentacaoLivro
from app.sessions.models import Session
from app.inventory.models import SessaoInventario, ItemInventario
from app.notifications.models import Alerta
from app.rfid.models import LogAcesso
from app.admin.models import Config

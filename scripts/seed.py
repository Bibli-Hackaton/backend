import asyncio
import uuid
import sys
import os

# Adiciona a raiz do projeto no PYTHONPATH para poder importar o 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker
from app.auth.models import User, UserRole
from app.core.security import get_password_hash
from app.books.models import Book, BookEstado
from app.admin.models import Config

async def seed_users():
    async with async_session_maker() as session:
        # Create users
        admin_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
        users = [
            User(id=admin_id, nome="Administrador", email="admin@biblioteca.com", senha_hash=get_password_hash("admin123"), role=UserRole.admin),
            User(id=uuid.UUID('00000000-0000-0000-0000-000000000002'), nome="Vigilante Silva", email="vigilante@biblioteca.com", senha_hash=get_password_hash("vigilante123"), role=UserRole.vigilante),
            User(id=uuid.UUID('00000000-0000-0000-0000-000000000003'), nome="João Aluno", email="joao@biblioteca.com", senha_hash=get_password_hash("aluno123"), role=UserRole.aluno),
            User(id=uuid.UUID('00000000-0000-0000-0000-000000000004'), nome="Maria Aluna", email="maria@biblioteca.com", senha_hash=get_password_hash("aluno123"), role=UserRole.aluno),
            User(id=uuid.UUID('00000000-0000-0000-0000-000000000005'), nome="Pedro Aluno", email="pedro@biblioteca.com", senha_hash=get_password_hash("aluno123"), role=UserRole.aluno),
        ]
        
        for u in users:
            session.add(u)
        
        await session.commit()
            
        # Create 10 books
        books = [
            Book(id=uuid.uuid4(), titulo="Clean Code", autor="Robert C. Martin", isbn="978-0132350884", rfid_tag="TAG-1001", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="The Pragmatic Programmer", autor="Andrew Hunt", isbn="978-0135957059", rfid_tag="TAG-1002", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="Design Patterns", autor="Erich Gamma", isbn="978-0201633610", rfid_tag="TAG-1003", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="Refactoring", autor="Martin Fowler", isbn="978-0134757599", rfid_tag="TAG-1004", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="Domain-Driven Design", autor="Eric Evans", isbn="978-0321125217", rfid_tag="TAG-1005", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="Head First Design Patterns", autor="Eric Freeman", isbn="978-0596007126", rfid_tag="TAG-1006", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="Code Complete", autor="Steve McConnell", isbn="978-0735619678", rfid_tag="TAG-1007", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="Introduction to Algorithms", autor="Thomas H. Cormen", isbn="978-0262033848", rfid_tag="TAG-1008", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="Structure and Interpretation", autor="Harold Abelson", isbn="978-0262510875", rfid_tag="TAG-1009", estado=BookEstado.disponivel),
            Book(id=uuid.uuid4(), titulo="The Mythical Man-Month", autor="Frederick P. Brooks Jr.", isbn="978-0201835953", rfid_tag="TAG-1010", estado=BookEstado.disponivel),
        ]
        
        for b in books:
            session.add(b)

        # Create configurations
        configs = [
            Config(chave="tempo_sessao_min", valor="30", descricao="Tempo padrão de uma sessão de estudo em minutos", atualizado_por=admin_id),
            Config(chave="max_dias_emprestimo", valor="7", descricao="Número máximo de dias para um empréstimo", atualizado_por=admin_id)
        ]
        
        for c in configs:
            session.add(c)
        
        await session.commit()
        print("Usuários, Livros e Configurações inseridos com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed_users())

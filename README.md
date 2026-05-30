# Biblioteca Hackathon Backend

Backend desenvolvido em **FastAPI** para o projeto da Biblioteca.

## Tecnologias Principais
- FastAPI
- SQLAlchemy + Alembic (Migrations)
- PostgreSQL (Supabase)
- MQTT (Eclipse Mosquitto)
- Redis

## Setup Local

1. Crie e ative o ambiente virtual:
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate   # Linux/Mac
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Crie o arquivo `.env` baseado no exemplo:
```bash
cp .env.example .env
```
*(Atualize as variáveis com os dados reais de conexão).* 

4. Suba os serviços auxiliares (Redis e Mosquitto):
```bash
make up
```

5. Rode a API:
```bash
uvicorn app.main:app --reload
```
Acesse a documentação interativa (Swagger) em: [http://localhost:8000/docs](http://localhost:8000/docs)

## WebSocket (Totem e Vigilante)
- Canais: `/ws/totem`, `/ws/vigilante`, `/ws/admin`.
- O cliente deve implementar reconexao automatica em caso de queda.

## Migrations (Alembic)
Para gerar uma nova migration após alterar algum modelo (`app/models/`):
```bash
make makemigrations MSG="Sua mensagem de commit"
```

Para aplicar as migrations no banco:
```bash
make migrate
```

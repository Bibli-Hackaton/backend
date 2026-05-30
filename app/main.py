from fastapi import FastAPI

from app.routers import books, users


app = FastAPI(title="Backend", version="0.1.0")

app.include_router(users.router)
app.include_router(books.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World!"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
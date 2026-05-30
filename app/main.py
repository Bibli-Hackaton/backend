from fastapi import FastAPI


app = FastAPI(title="Backend", version="0.1.0")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World!"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
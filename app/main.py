from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.users import router as users_router
from app.db.database import AsyncSessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Niramaya-AI Backend", lifespan=lifespan)
app.include_router(users_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "connected"}

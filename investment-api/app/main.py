from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.companies import router as companies_router
from app.api.dividends import router as dividends_router
from app.api.reports import router as reports_router
from app.api.sectors import router as sectors_router
from app.config import settings
from app.db import Base, engine
from app.models import *  # noqa: F401, F403 — register all models with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Investment API", version="0.1.0", lifespan=lifespan)

app.include_router(sectors_router)
app.include_router(companies_router)
app.include_router(reports_router)
app.include_router(dividends_router)


@app.get("/health")
async def health():
    return {"status": "ok"}

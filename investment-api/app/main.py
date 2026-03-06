import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analytics import router as analytics_router
from app.api.catalysts import router as catalysts_router
from app.api.companies import router as companies_router
from app.api.dividends import router as dividends_router
from app.api.jobs import router as jobs_router
from app.api.news import router as news_router
from app.api.prices import router as prices_router
from app.api.reports import router as reports_router
from app.api.sectors import router as sectors_router
from app.api.signals import router as signals_router
from app.admin import setup_admin
from app.config import settings
from app.api.deps import get_db
from app.db import Base, engine
from app.models import *  # noqa: F401, F403 — register all models with Base.metadata

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Start scheduler in non-debug (production) mode
    scheduler = None
    if not settings.debug:
        from app.jobs.scheduler import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
        logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


app = FastAPI(title="Investment API", version="0.1.0", lifespan=lifespan)

setup_admin(app, engine)

app.include_router(sectors_router)
app.include_router(companies_router)
app.include_router(reports_router)
app.include_router(dividends_router)
app.include_router(catalysts_router)
app.include_router(prices_router)
app.include_router(news_router)
app.include_router(signals_router)
app.include_router(jobs_router)
app.include_router(analytics_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Health check with DB connectivity verification."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "disconnected", "error": str(e)},
        )

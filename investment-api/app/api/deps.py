import hmac
from collections.abc import AsyncIterator

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def require_api_key(x_api_key: str = Header()) -> str:
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


async def get_company(ticker: str, db: AsyncSession):
    """Shared helper to look up a company by ticker, raising 404 if not found."""
    from app.models import Company

    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

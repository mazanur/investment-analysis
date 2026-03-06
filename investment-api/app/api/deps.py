from collections.abc import AsyncIterator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


async def require_api_key(x_api_key: str = Header()) -> str:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

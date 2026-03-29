from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.config import SraoshaSettings, settings
from sraosha.db import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_settings() -> SraoshaSettings:
    return settings


async def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    app_settings: SraoshaSettings = Depends(get_settings),
) -> None:
    if app_settings.API_KEY and x_api_key != app_settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

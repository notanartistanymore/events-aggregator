from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from events_aggregator.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    """Synchronous engine retained for Alembic migrations."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_async_engine():
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_async_engine(), expire_on_commit=False)


async def get_db():
    async with get_session_factory()() as session:
        yield session

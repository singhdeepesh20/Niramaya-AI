from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by ORM models and Alembic metadata."""


engine_options = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("postgresql+"):
    # Fail quickly when PostgreSQL is down instead of leaving signup requests pending.
    engine_options["connect_args"] = {"connect_timeout": 5}

engine = create_async_engine(settings.DATABASE_URL, **engine_options)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield one isolated session per request and always close it afterwards."""
    async with AsyncSessionLocal() as session:
        yield session

"""Explicit local-development table creation; run with python -m app.db.init_db."""
import asyncio

from app.db.database import engine
from app.db.models import Base, User  # Import models so they register with Base.metadata.


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())

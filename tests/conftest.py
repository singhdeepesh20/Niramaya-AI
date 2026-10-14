import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-value-with-more-than-32-bytes"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ISSUER"] = ""
os.environ["JWT_AUDIENCE"] = ""
os.environ["FRONTEND_ORIGINS"] = "[]"

from app.database import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.user import models  # noqa: E402,F401
from app.health import models as health_models  # noqa: E402,F401
from app.documents import models as document_models  # noqa: E402,F401


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_file = tmp_path / "test.sqlite3"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_file}",
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def create_schema() -> None:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    app = create_app()
    app.state.test_session_factory = session_factory

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())

"""
tests/conftest.py
─────────────────
Shared pytest fixtures for PlaceMate AI tests.

Key design decisions:
  - Each test gets a FRESH in-memory SQLite database. Tests cannot interfere
    with each other, and no test leaves data in the development database.
  - The async client uses httpx.AsyncClient with the real FastAPI app but
    an overridden database dependency.
  - AI (Gemini) is NEVER called in tests. The gemini_client module is
    monkeypatched at the session level.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app

# ── In-memory test database ────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a fresh in-memory SQLite engine for each test function."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        from app import models  # noqa: F401 — ensure models are registered
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Yield a database session connected to the test database."""
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    """
    Return an AsyncClient that uses the real FastAPI app
    but with the test database injected via dependency override.
    """
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def register_and_login(client: AsyncClient, email: str, password: str) -> str:
    """Register a student and return a Bearer token."""
    await client.post("/auth/register", json={"email": email, "password": password})
    resp = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

"""
app/database.py
───────────────
SQLAlchemy 2.x async database setup.

Architecture note
─────────────────
We use the async engine + async session pattern because FastAPI is an async
framework. Using async sessions means database queries do not block the event
loop, so the server can handle many requests concurrently.

Key objects exported:
  engine       – the underlying database connection pool
  AsyncSession – a factory for individual database sessions
  Base         – the declarative base all ORM models inherit from
  get_db       – a FastAPI dependency that yields a session per request
  init_db      – called at startup to create all tables
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
# connect_args={"check_same_thread": False} is required for SQLite only.
# When we later switch to PostgreSQL this argument is simply removed.
engine = create_async_engine(
    settings.database_url,
    echo=(settings.app_env == "development"),   # log SQL in dev, not in prod
    connect_args={"check_same_thread": False},
)

# ── Session factory ───────────────────────────────────────────────────────────
# expire_on_commit=False keeps model attributes accessible after commit,
# which matters when we return Pydantic schemas from route handlers.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All SQLAlchemy ORM models inherit from this class."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db():
    """
    Yields one database session per request, then closes it.

    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Table creation ────────────────────────────────────────────────────────────
async def init_db() -> None:
    """
    Creates all tables defined in ORM models.

    Called once at application startup (see app/main.py lifespan hook).
    For a production deployment you would use Alembic migrations instead,
    but create_all() is fine for the local SQLite MVP.
    """
    async with engine.begin() as conn:
        # Import models here so Base.metadata knows about them
        from app import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

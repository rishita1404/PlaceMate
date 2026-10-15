"""
app/main.py
───────────
FastAPI application entry point for PlaceMate AI.

This file:
  1. Creates the FastAPI app instance.
  2. Registers all API routers.
  3. Configures CORS (so the Streamlit UI can call the API).
  4. Sets up the lifespan handler (startup/shutdown).
  5. Defines the health-check endpoint.

Architecture note
─────────────────
The main.py file is intentionally thin. Business logic belongs in service
modules. Route logic belongs in api/ modules. This file only wires things
together.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run startup tasks before the first request, and cleanup after shutdown.

    Startup:
      - Create the uploads directory.
      - Initialise the database (create tables if they don't exist).

    Shutdown:
      - Nothing special needed for SQLite MVP; add cleanup here later.
    """
    import os
    os.makedirs(settings.upload_dir, exist_ok=True)

    await init_db()
    print(f"✅  PlaceMate AI started — AI features {'enabled' if settings.ai_enabled else 'disabled (no GEMINI_API_KEY)'}")

    yield  # app runs here

    # shutdown
    print("PlaceMate AI shutting down.")


app = FastAPI(
    title="PlaceMate AI",
    description=(
        "AI-powered career assistance platform for college students. "
        "Combines resume analysis, job matching, eligibility checking, "
        "interview preparation, and application tracking."
    ),
    version="0.1.0-mvp",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Streamlit UI (running on port 8501) to call the FastAPI backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.auth import router as auth_router
from app.api.profiles import router as profiles_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.applications import router as applications_router
from app.api.admin import router as admin_router

app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(admin_router)


# ── Health check ──────────────────────────────────────────────────────────────
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import HealthOut


@app.get("/health", response_model=HealthOut, tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Verify that the application and database are running.
    Returns AI availability status without exposing any credentials.
    """
    # Test the database connection with a lightweight query
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        ai_enabled=settings.ai_enabled,
    )


from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root requests to interactive documentation."""
    return RedirectResponse(url="/docs")

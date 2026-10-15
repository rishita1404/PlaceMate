"""
app/config.py
─────────────
Central configuration for PlaceMate AI.

All runtime settings are read from environment variables (or a .env file).
This means we never hardcode secrets in Python code.

How it works:
  pydantic-settings reads the .env file automatically and maps each variable
  to a typed Python attribute. If a required variable is missing the app
  refuses to start, which is safer than silently using None.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    secret_key: str = "change-me-in-dot-env"          # used for JWT signing
    access_token_expire_minutes: int = 60 * 8          # 8 hours

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./placemate.db"

    # ── Gemini ───────────────────────────────────────────────────────────────
    gemini_api_key: str = ""                           # empty → AI features disabled
    gemini_model: str = "gemini-1.5-flash"

    # ── File upload ──────────────────────────────────────────────────────────
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10

    # ── CORS ─────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    # pydantic-settings v2: tell it to read from .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return CORS origins as a Python list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        """True only when a Gemini key is configured."""
        return bool(self.gemini_api_key and self.gemini_api_key != "your-gemini-api-key-here")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    Using lru_cache means the .env file is parsed once, not on every request.
    FastAPI dependency-injection calls this via Depends(get_settings).
    """
    return Settings()

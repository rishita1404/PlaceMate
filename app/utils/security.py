"""
app/utils/security.py
─────────────────────
Password hashing and JWT token handling.

Why bcrypt for passwords?
  bcrypt is a deliberately slow hashing algorithm. This matters because
  if an attacker ever gets a copy of your database, they cannot reverse
  hashes quickly. Never store plaintext passwords.

Why JWT for sessions?
  JSON Web Tokens let the client prove who it is without the server
  storing session state. The token is signed with SECRET_KEY, so we
  can verify it is genuine without a database lookup on every request.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.schemas import TokenData

settings = get_settings()

# ── Password hashing ──────────────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of the plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored hash."""
    return _pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────
ALGORITHM = "HS256"


def create_access_token(
    user_id: int,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT containing user_id and role.

    The token expires after `expires_delta` (default: from settings).
    FastAPI routes decode this to identify the caller.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decode and verify a JWT.

    Returns None if the token is invalid, expired, or tampered with.
    Never raises — callers must check for None.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id_str: Optional[str] = payload.get("sub")
        role_str: Optional[str] = payload.get("role")
        if user_id_str is None:
            return None
        from app.models import UserRole
        return TokenData(user_id=int(user_id_str), role=UserRole(role_str))
    except JWTError:
        return None

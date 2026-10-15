"""
app/utils/deps.py
─────────────────
Reusable FastAPI dependency functions.

FastAPI dependencies are functions you inject into route handlers with
`Depends(...)`. They run before the handler and can:
  - Validate inputs.
  - Authenticate the caller.
  - Yield database sessions.
  - Enforce authorization (student vs admin).

All authentication and authorization logic lives here, not scattered
across individual route files.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserRole
from app.utils.security import decode_access_token

# FastAPI reads the Bearer token from the Authorization header.
# tokenUrl tells the auto-generated docs where to get a token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Decode the JWT and load the matching User from the database.

    Raises HTTP 401 if:
    - The token is missing, malformed, or expired.
    - The user no longer exists (e.g., deleted account).
    - The account is deactivated.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_access_token(token)
    if token_data is None or token_data.user_id is None:
        raise credentials_error

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_error

    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Ensure the caller is an administrator.

    Any non-admin student who calls an admin-only endpoint gets HTTP 403.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user


# Typed shorthand aliases — use these in route function signatures.
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
DB = Annotated[AsyncSession, Depends(get_db)]

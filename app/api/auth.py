"""
app/api/auth.py
───────────────
Authentication routes: register and login.

POST /auth/register  — create a new student account
POST /auth/login     — exchange credentials for a JWT

Design decisions
────────────────
- New accounts always get role=student. Admins must be created directly
  in the database or through a separate admin-only promotion endpoint
  (not in scope for MVP day 1).
- We return a Bearer token, not a session cookie, because this makes
  testing with curl / Postman / Streamlit simpler.
- We deliberately do NOT return the hashed password or any internal field
  in the response.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserRole
from app.schemas import Token, UserOut, UserRegister
from app.utils.deps import DB
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: DB):
    """
    Create a new student account.

    Returns the new user record (without the password hash).
    Raises 409 if the email is already registered.
    """
    # Check for duplicate email
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=UserRole.student,
    )
    db.add(user)
    await db.flush()   # get the auto-generated id before commit
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DB,
):
    """
    Exchange email + password for a JWT Bearer token.

    Uses OAuth2PasswordRequestForm so the /docs page shows a login form.
    The 'username' field in the form is interpreted as email.
    Raises 401 for any invalid combination (we do NOT say which field is wrong,
    to prevent user enumeration).
    """
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None or not verify_password(form.password, user.hashed_password):
        raise invalid
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    token = create_access_token(user_id=user.id, role=user.role.value)
    return Token(access_token=token)

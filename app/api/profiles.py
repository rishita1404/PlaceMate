"""
app/api/profiles.py
────────────────────
Student profile management routes.

GET  /profile       — read the current student's profile
PUT  /profile       — update profile fields
POST /profile/confirm — mark profile as confirmed (locks it for AI use)

Design notes
────────────
- A profile is created automatically on first GET if it does not exist.
  This simplifies the client — students never have to call a separate
  "create profile" endpoint.
- Only confirmed profiles can be used for tailored resume generation and
  application drafts (enforced in service layers).
- Students can only access their own profile. Admins could access any
  profile for support purposes, but that is out of scope for MVP.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.models import StudentProfile
from app.schemas import MessageOut, ProfileOut, ProfileUpdate
from app.utils.deps import CurrentUser, DB

router = APIRouter(prefix="/profile", tags=["Profile"])


async def _get_or_create_profile(user_id: int, db) -> StudentProfile:
    """Return the student's profile, creating an empty one if it doesn't exist."""
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = StudentProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
    return profile


@router.get("", response_model=ProfileOut)
async def get_profile(current_user: CurrentUser, db: DB):
    """
    Return the student's career profile.
    Creates an empty profile on first call.
    """
    profile = await _get_or_create_profile(current_user.id, db)
    return profile


@router.put("", response_model=ProfileOut)
async def update_profile(body: ProfileUpdate, current_user: CurrentUser, db: DB):
    """
    Update profile fields.

    Any subset of fields may be provided — omitted fields are not changed.
    Setting is_confirmed=True via this endpoint is NOT allowed; use
    POST /profile/confirm instead (this separates intentional confirmation
    from accidental payload inclusion).
    """
    profile = await _get_or_create_profile(current_user.id, db)

    # Prevent accidental confirmation through the update endpoint
    if body.is_confirmed is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /profile/confirm to confirm your profile.",
        )

    # Apply each provided field
    if body.institution is not None:
        profile.institution = body.institution
    if body.degree is not None:
        profile.degree = body.degree
    if body.specialization is not None:
        profile.specialization = body.specialization
    if body.graduation_year is not None:
        profile.graduation_year = body.graduation_year
    if body.gpa is not None:
        profile.gpa = body.gpa
    if body.gpa_type is not None:
        profile.gpa_type = body.gpa_type
    if body.skills is not None:
        profile.skills = body.skills
    if body.experience is not None:
        profile.experience = [e.model_dump() for e in body.experience]
    if body.projects is not None:
        profile.projects = [p.model_dump() for p in body.projects]
    if body.certifications is not None:
        profile.certifications = body.certifications
    if body.preferences is not None:
        profile.preferences = body.preferences

    await db.flush()
    await db.refresh(profile)
    return profile


@router.post("/confirm", response_model=MessageOut)
async def confirm_profile(current_user: CurrentUser, db: DB):
    """
    Mark the student's profile as confirmed.

    After confirmation, the profile can be used as the factual basis for
    tailored resumes, application drafts, and matching explanations.

    Students can re-confirm after editing if they update their information.
    """
    profile = await _get_or_create_profile(current_user.id, db)

    if not profile.skills and not profile.degree:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please add at least some skills or education before confirming.",
        )

    profile.is_confirmed = True
    profile.confirmed_at = datetime.now(timezone.utc)
    await db.flush()
    return MessageOut(message="Profile confirmed. You can now use it for job matching and applications.")

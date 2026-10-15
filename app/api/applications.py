"""
app/api/applications.py
───────────────────────
Application tracking routes.

POST /applications            — create a draft application
GET  /applications            — list the student's applications
GET  /applications/{id}       — application detail
PATCH /applications/{id}      — update status or draft content
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.models import Application, ApplicationStatus, Job
from app.schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate
from app.utils.deps import CurrentUser, DB

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(body: ApplicationCreate, current_user: CurrentUser, db: DB):
    """
    Create a draft application for a job.

    Checks for duplicate active applications (student cannot have two
    non-withdrawn, non-rejected applications for the same job).
    """
    # Verify job exists
    job_result = await db.execute(select(Job).where(Job.id == body.job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    # Duplicate check — allow re-application only after withdrawal or rejection
    existing_result = await db.execute(
        select(Application).where(
            Application.user_id == current_user.id,
            Application.job_id == body.job_id,
            Application.status.not_in([ApplicationStatus.withdrawn, ApplicationStatus.rejected]),
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active application for this job.",
        )

    app = Application(
        user_id=current_user.id,
        job_id=body.job_id,
        status=ApplicationStatus.draft,
        notes=body.notes,
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)
    return app


@router.get("", response_model=list[ApplicationOut])
async def list_applications(current_user: CurrentUser, db: DB):
    """List all applications belonging to the current student."""
    result = await db.execute(
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(Application.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(application_id: int, current_user: CurrentUser, db: DB):
    """Return one application. Enforces ownership."""
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return app


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: int,
    body: ApplicationUpdate,
    current_user: CurrentUser,
    db: DB,
):
    """
    Update an application's status, notes, draft content, or confirmation.

    Rules:
    - 'submitted_confirmed' requires a confirmation_reference.
    - Cannot transition from terminal states (offer, rejected, withdrawn).
    - Submitted_at is set automatically when status → submitted_confirmed.
    """
    from datetime import datetime, timezone

    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    TERMINAL = {ApplicationStatus.offer, ApplicationStatus.rejected, ApplicationStatus.withdrawn}
    if app.status in TERMINAL and body.status is not None and body.status != app.status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot change status from terminal state '{app.status.value}'.",
        )

    if body.status == ApplicationStatus.submitted_confirmed:
        if not body.confirmation_reference and not app.confirmation_reference:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A confirmation_reference is required to mark an application as submitted.",
            )
        if app.submitted_at is None:
            app.submitted_at = datetime.now(timezone.utc)

    if body.status is not None:
        app.status = body.status
    if body.notes is not None:
        app.notes = body.notes
    if body.confirmation_reference is not None:
        app.confirmation_reference = body.confirmation_reference
    if body.draft_data is not None:
        app.draft_data = body.draft_data

    await db.flush()
    await db.refresh(app)
    return app

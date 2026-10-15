"""
app/api/jobs.py
───────────────
Job listing and job-detail routes.

GET /jobs           — browse active jobs with optional filters
GET /jobs/{id}      — full detail of one job
GET /jobs/{id}/match           — match score for the current student
GET /jobs/{id}/eligibility     — general + college eligibility check
GET /jobs/{id}/interview-questions — interview prep resources
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Job, ListingStatus, StudentProfile
from app.schemas import EligibilityResult, InterviewQuestionsResponse, JobListOut, JobOut, MatchResult
from app.services.eligibility_service import check_eligibility
from app.services.interview_service import get_interview_questions
from app.services.matching_service import compute_match
from app.utils.deps import CurrentUser, DB

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobListOut])
async def list_jobs(
    current_user: CurrentUser,
    db: DB,
    job_type: Optional[str] = Query(None, description="internship | full_time | part_time | contract"),
    location: Optional[str] = Query(None, description="Partial location match"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Return active job listings with optional filters.
    Joins company name for display without exposing unnecessary data.
    """
    from app.models import Company

    query = (
        select(Job, Company.name.label("company_name"))
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Job.listing_status == ListingStatus.active)
    )

    if job_type:
        query = query.where(Job.job_type == job_type)
    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))

    query = query.order_by(Job.retrieved_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(query)).all()

    results = []
    for job, company_name in rows:
        results.append(
            JobListOut(
                id=job.id,
                title=job.title,
                company_name=company_name,
                location=job.location,
                job_type=job.job_type,
                deadline=job.deadline,
                listing_status=job.listing_status,
            )
        )
    return results


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, current_user: CurrentUser, db: DB):
    """Return full details of a single job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None or job.listing_status == ListingStatus.removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.get("/{job_id}/match", response_model=MatchResult)
async def get_job_match(job_id: int, current_user: CurrentUser, db: DB):
    """
    Compute and return the explainable match score for this job.
    Requires a confirmed student profile.
    """
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None or not profile.is_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please complete and confirm your profile before viewing match scores.",
        )

    from app.models import Company
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one_or_none()

    return compute_match(job=job, profile=profile, company_name=company.name if company else None)


@router.get("/{job_id}/eligibility", response_model=EligibilityResult)
async def get_job_eligibility(job_id: int, current_user: CurrentUser, db: DB):
    """
    Return general + college eligibility checks for this job.
    Missing profile data results in 'unknown', not 'pass'.
    """
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    return await check_eligibility(job=job, profile=profile, db=db)


@router.get("/{job_id}/interview-questions", response_model=InterviewQuestionsResponse)
async def get_interview_questions_route(job_id: int, current_user: CurrentUser, db: DB):
    """
    Return interview preparation resources for a job.

    Source-backed, AI-generated, and unverified questions are returned
    in separate lists so the UI can label them clearly.
    AI-generated questions are created from the job description.
    """
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return await get_interview_questions(job=job, db=db)

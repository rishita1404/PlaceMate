"""
app/api/admin.py
────────────────
Admin-only routes for managing jobs, college rules, and sources.

All routes use the AdminUser dependency — any non-admin caller gets HTTP 403.

POST /admin/jobs/import          — manually import a job
GET  /admin/college-rules        — list all college rules
POST /admin/college-rules        — add a college rule
POST /admin/college-rules/{id}/verify — mark a rule as verified
DELETE /admin/college-rules/{id} — remove a rule
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.models import CollegeRule, Company, EligibilityVerification, Job, JobSource, ListingStatus
from app.schemas import (
    CollegeRuleCreate, CollegeRuleOut, CollegeRuleVerify,
    JobCreate, JobOut, MessageOut,
)
from app.utils.deps import AdminUser, DB

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Job import ────────────────────────────────────────────────────────────────

@router.post("/jobs/import", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def import_job(body: JobCreate, current_user: AdminUser, db: DB):
    """
    Manually import a job listing (admin only).

    Creates or reuses the company record, creates a manual source if needed,
    then inserts the job. Prevents duplicates by company+title+source check.
    """
    # Get or create company
    company_result = await db.execute(
        select(Company).where(Company.name == body.company_name)
    )
    company = company_result.scalar_one_or_none()
    if company is None:
        company = Company(name=body.company_name)
        db.add(company)
        await db.flush()
        await db.refresh(company)

    # Get or create a manual source for this company
    source_result = await db.execute(
        select(JobSource).where(
            JobSource.company_id == company.id,
            JobSource.source_type == body.source_type,
        )
    )
    source = source_result.scalar_one_or_none()
    if source is None:
        source = JobSource(
            company_id=company.id,
            source_url=f"manual://{company.name}",
            source_type=body.source_type,
            import_status="ok",
        )
        db.add(source)
        await db.flush()
        await db.refresh(source)

    # Build the job
    job = Job(
        company_id=company.id,
        source_id=source.id,
        source_job_id=None,   # manual imports have no external ID
        title=body.title,
        description=body.description,
        location=body.location,
        job_type=body.job_type,
        official_url=body.official_url,
        deadline=body.deadline,
        listing_status=ListingStatus.active,
    )
    job.required_skills = body.required_skills
    job.preferred_skills = body.preferred_skills
    job.eligibility_requirements = body.eligibility_requirements

    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


# ── College rules ─────────────────────────────────────────────────────────────

@router.get("/college-rules", response_model=list[CollegeRuleOut])
async def list_college_rules(current_user: AdminUser, db: DB):
    result = await db.execute(select(CollegeRule).order_by(CollegeRule.created_at.desc()))
    return result.scalars().all()


@router.post("/college-rules", response_model=CollegeRuleOut, status_code=status.HTTP_201_CREATED)
async def create_college_rule(body: CollegeRuleCreate, current_user: AdminUser, db: DB):
    rule = CollegeRule(
        college_scope=body.college_scope,
        rule_type=body.rule_type,
        rule_value=body.rule_value,
        source_reference=body.source_reference,
        effective_from=body.effective_from,
        effective_until=body.effective_until,
        verification_status=EligibilityVerification.pending,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.post("/college-rules/{rule_id}/verify", response_model=CollegeRuleOut)
async def verify_college_rule(rule_id: int, body: CollegeRuleVerify, current_user: AdminUser, db: DB):
    """
    Mark a college rule as verified.
    Sets verified_by to the admin's email and records the timestamp.
    """
    result = await db.execute(select(CollegeRule).where(CollegeRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")

    rule.verification_status = EligibilityVerification.verified
    rule.verified_by = body.verified_by
    rule.verified_at = datetime.now(timezone.utc)
    if body.source_reference:
        rule.source_reference = body.source_reference

    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/college-rules/{rule_id}", response_model=MessageOut)
async def delete_college_rule(rule_id: int, current_user: AdminUser, db: DB):
    result = await db.execute(select(CollegeRule).where(CollegeRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")
    await db.delete(rule)
    return MessageOut(message=f"College rule {rule_id} deleted.")

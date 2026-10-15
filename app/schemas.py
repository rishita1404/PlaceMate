"""
app/schemas.py
──────────────
Pydantic v2 schemas for FastAPI request validation and response serialization.

Why separate schemas from ORM models?
  ORM models describe what the database stores.
  Pydantic schemas describe what the API accepts and returns.
  They are deliberately different:
    - We never expose hashed_password in a response.
    - We never allow a user to set their own role via the API.
    - Response schemas may combine fields from multiple ORM models.

Naming convention:
  <Entity>Create  — body of a POST request (creating a resource)
  <Entity>Update  — body of a PUT/PATCH request
  <Entity>Out     — response to the client
  <Entity>DB      — internal schema that includes DB-only fields
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import (
    ApplicationStatus, EligibilityVerification, JobType,
    ListingStatus, QuestionProvenance, ResumeStatus, UserRole,
)


# ══════════════════════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════════════════════

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="At least 8 characters")

    @field_validator("password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        if v.lower() in ("password", "12345678", "password1"):
            raise ValueError("Please choose a stronger password.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Decoded JWT payload — used internally, never sent to the client."""
    user_id: Optional[int] = None
    role: Optional[UserRole] = None


class UserOut(BaseModel):
    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# Student Profile
# ══════════════════════════════════════════════════════════════════════════════

class ExperienceItem(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None   # "YYYY-MM" or free text
    end_date: Optional[str] = None
    description: Optional[str] = None
    is_internship: bool = False


class ProjectItem(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: list[str] = []
    url: Optional[str] = None


class ProfileUpdate(BaseModel):
    """Fields the student can update in their profile."""
    institution: Optional[str] = None
    degree: Optional[str] = None
    specialization: Optional[str] = None
    graduation_year: Optional[int] = Field(None, ge=1990, le=2040)
    gpa: Optional[float] = Field(None, ge=0.0, le=10.0)
    gpa_type: Optional[str] = Field(None, pattern="^(gpa|percentage)$")
    skills: Optional[list[str]] = None
    experience: Optional[list[ExperienceItem]] = None
    projects: Optional[list[ProjectItem]] = None
    certifications: Optional[list[str]] = None
    preferences: Optional[dict] = None
    is_confirmed: Optional[bool] = None


class ProfileOut(BaseModel):
    id: int
    user_id: int
    institution: Optional[str]
    degree: Optional[str]
    specialization: Optional[str]
    graduation_year: Optional[int]
    gpa: Optional[float]
    gpa_type: Optional[str]
    skills: list[str]
    experience: list[dict]
    projects: list[dict]
    certifications: list[str]
    preferences: dict
    is_confirmed: bool
    confirmed_at: Optional[datetime]
    updated_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# Resume
# ══════════════════════════════════════════════════════════════════════════════

class ResumeOut(BaseModel):
    id: int
    user_id: int
    original_filename: str
    file_size_bytes: int
    page_count: Optional[int]
    status: ResumeStatus
    error_message: Optional[str]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ResumeExtractOut(BaseModel):
    resume_id: int
    status: ResumeStatus
    extracted_text_preview: Optional[str]   # first 500 chars, not full text
    page_count: Optional[int]
    message: str


# ══════════════════════════════════════════════════════════════════════════════
# Jobs
# ══════════════════════════════════════════════════════════════════════════════

class JobOut(BaseModel):
    id: int
    company_id: Optional[int]
    title: str
    description: Optional[str]
    location: Optional[str]
    job_type: Optional[JobType]
    required_skills: list[str]
    preferred_skills: list[str]
    eligibility_requirements: dict
    deadline: Optional[datetime]
    official_url: Optional[str]
    listing_status: ListingStatus
    retrieved_at: datetime

    model_config = {"from_attributes": True}


class JobListOut(BaseModel):
    """Compact job listing for browse views."""
    id: int
    title: str
    company_name: Optional[str]   # joined field
    location: Optional[str]
    job_type: Optional[JobType]
    deadline: Optional[datetime]
    listing_status: ListingStatus

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# Matching
# ══════════════════════════════════════════════════════════════════════════════

class SkillMatchDetail(BaseModel):
    matched_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    missing_preferred: list[str]


class MatchResult(BaseModel):
    job_id: int
    job_title: str
    company_name: Optional[str]
    overall_score: float = Field(ge=0.0, le=100.0)
    required_skill_score: float
    preferred_skill_score: float
    experience_score: float
    skill_detail: SkillMatchDetail
    supporting_projects: list[str]    # project names relevant to the job
    score_explanation: str
    eligibility_summary: str          # one-line human-readable


# ══════════════════════════════════════════════════════════════════════════════
# Eligibility
# ══════════════════════════════════════════════════════════════════════════════

class EligibilityCheck(BaseModel):
    criterion: str
    result: str           # "pass" | "fail" | "unknown"
    reason: str


class EligibilityResult(BaseModel):
    job_id: int
    general_checks: list[EligibilityCheck]
    college_checks: list[EligibilityCheck]
    overall_general: str        # "eligible" | "ineligible" | "incomplete"
    overall_college: str
    note: str


# ══════════════════════════════════════════════════════════════════════════════
# Applications
# ══════════════════════════════════════════════════════════════════════════════

class ApplicationCreate(BaseModel):
    job_id: int
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = None
    confirmation_reference: Optional[str] = None
    draft_data: Optional[dict] = None


class ApplicationOut(BaseModel):
    id: int
    user_id: int
    job_id: int
    status: ApplicationStatus
    notes: Optional[str]
    confirmation_reference: Optional[str]
    draft_data: dict
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
# Interview Questions
# ══════════════════════════════════════════════════════════════════════════════

class InterviewQuestionOut(BaseModel):
    id: int
    role: Optional[str]
    question_text: str
    question_category: Optional[str]
    provenance: QuestionProvenance
    source_url: Optional[str]
    year: Optional[int]

    model_config = {"from_attributes": True}


class InterviewQuestionsResponse(BaseModel):
    job_id: int
    source_backed: list[InterviewQuestionOut]
    ai_generated: list[InterviewQuestionOut]
    unverified: list[InterviewQuestionOut]
    disclaimer: str


# ══════════════════════════════════════════════════════════════════════════════
# Admin
# ══════════════════════════════════════════════════════════════════════════════

class JobCreate(BaseModel):
    """Admin-only: manually import a job listing."""
    company_name: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[JobType] = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    eligibility_requirements: dict = {}
    deadline: Optional[datetime] = None
    official_url: Optional[str] = None
    source_type: str = "manual"


class CollegeRuleCreate(BaseModel):
    college_scope: str
    rule_type: str
    rule_value: str
    source_reference: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class CollegeRuleOut(BaseModel):
    id: int
    college_scope: str
    rule_type: str
    rule_value: str
    source_reference: Optional[str]
    effective_from: Optional[datetime]
    effective_until: Optional[datetime]
    verification_status: EligibilityVerification
    verified_by: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class CollegeRuleVerify(BaseModel):
    verified_by: str
    source_reference: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# Generic responses
# ══════════════════════════════════════════════════════════════════════════════

class MessageOut(BaseModel):
    message: str


class HealthOut(BaseModel):
    status: str
    database: str
    ai_enabled: bool
    version: str = "0.1.0-mvp"

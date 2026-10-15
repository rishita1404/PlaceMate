"""
app/models.py
─────────────
SQLAlchemy ORM models for PlaceMate AI.

Every class here maps to one database table.
Read the docstring on each class to understand what it stores and why.

Design notes
────────────
- Relationships are explicit so we can navigate between tables in Python without
  writing raw SQL.
- Sensitive fields (passwords) are never stored in plaintext.
- Skills, preferences, and similar list-like fields are stored as JSON text
  for simplicity in SQLite. When we move to PostgreSQL we can switch to
  ARRAY or JSONB columns without changing the model layer logic.
- All timestamps are in UTC.
"""

import enum
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum as PGEnum, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Helpers ───────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════════════
# Enumerations
# ══════════════════════════════════════════════════════════════════════════════

class UserRole(str, enum.Enum):
    student = "student"
    admin = "admin"


class ResumeStatus(str, enum.Enum):
    uploaded = "uploaded"           # file received, not yet processed
    extracting = "extracting"       # text extraction in progress
    extracted = "extracted"         # raw text available
    ai_processing = "ai_processing" # Gemini extraction in progress
    profile_suggested = "profile_suggested"  # AI has proposed fields
    confirmed = "confirmed"         # student has reviewed and confirmed
    failed = "failed"               # extraction or processing error


class JobType(str, enum.Enum):
    internship = "internship"
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"


class ListingStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    removed = "removed"
    draft = "draft"


class ApplicationStatus(str, enum.Enum):
    draft = "draft"
    ready_for_review = "ready_for_review"
    application_started = "application_started"
    submitted_confirmed = "submitted_confirmed"
    pending_verification = "pending_verification"
    interview = "interview"
    assessment = "assessment"
    rejected = "rejected"
    offer = "offer"
    withdrawn = "withdrawn"


class EligibilityVerification(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    outdated = "outdated"


class QuestionProvenance(str, enum.Enum):
    source_backed = "source_backed"   # has URL / reference
    ai_generated = "ai_generated"     # made by Gemini
    unverified = "unverified"         # community / unknown origin


# ══════════════════════════════════════════════════════════════════════════════
# Users
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """
    Represents a registered user — either a student or an administrator.

    Why store role here?
    We check role on almost every request, so it belongs on the User row
    rather than in a separate roles table (YAGNI for MVP).
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(PGEnum(UserRole), default=UserRole.student, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # ── Relationships ─────────────────────────────────────────────────────────
    profile: Mapped[Optional["StudentProfile"]] = relationship(
        "StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    resumes: Mapped[list["Resume"]] = relationship(
        "Resume", back_populates="user", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


# ══════════════════════════════════════════════════════════════════════════════
# Student Profile
# ══════════════════════════════════════════════════════════════════════════════

class StudentProfile(Base):
    """
    Stores a student's career profile.

    This is the factual basis for matching and application generation.
    All fields must be student-confirmed before they can be used for
    tailored resumes or applications — the `is_confirmed` flag tracks this.

    JSON columns: skills, experience, projects, certifications, preferences
    are stored as JSON strings so we can keep the schema simple in SQLite
    while supporting rich nested data.
    """
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # ── Education ─────────────────────────────────────────────────────────────
    institution: Mapped[Optional[str]] = mapped_column(String(255))
    degree: Mapped[Optional[str]] = mapped_column(String(255))
    specialization: Mapped[Optional[str]] = mapped_column(String(255))
    graduation_year: Mapped[Optional[int]] = mapped_column(Integer)
    gpa: Mapped[Optional[float]] = mapped_column(Float)           # or percentage
    gpa_type: Mapped[Optional[str]] = mapped_column(String(10))   # "gpa" | "percentage"

    # ── Skills / experience (JSON strings) ────────────────────────────────────
    # Example skills value: '["Python", "SQL", "React"]'
    _skills: Mapped[Optional[str]] = mapped_column("skills", Text, default="[]")
    _experience: Mapped[Optional[str]] = mapped_column("experience", Text, default="[]")
    _projects: Mapped[Optional[str]] = mapped_column("projects", Text, default="[]")
    _certifications: Mapped[Optional[str]] = mapped_column("certifications", Text, default="[]")
    _preferences: Mapped[Optional[str]] = mapped_column("preferences", Text, default="{}")

    # ── Verification ──────────────────────────────────────────────────────────
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="profile")

    # ── JSON property helpers ─────────────────────────────────────────────────
    @property
    def skills(self) -> list[str]:
        return json.loads(self._skills or "[]")

    @skills.setter
    def skills(self, value: list[str]) -> None:
        self._skills = json.dumps(value)

    @property
    def experience(self) -> list[dict]:
        return json.loads(self._experience or "[]")

    @experience.setter
    def experience(self, value: list[dict]) -> None:
        self._experience = json.dumps(value)

    @property
    def projects(self) -> list[dict]:
        return json.loads(self._projects or "[]")

    @projects.setter
    def projects(self, value: list[dict]) -> None:
        self._projects = json.dumps(value)

    @property
    def certifications(self) -> list[str]:
        return json.loads(self._certifications or "[]")

    @certifications.setter
    def certifications(self, value: list[str]) -> None:
        self._certifications = json.dumps(value)

    @property
    def preferences(self) -> dict:
        return json.loads(self._preferences or "{}")

    @preferences.setter
    def preferences(self, value: dict) -> None:
        self._preferences = json.dumps(value)

    def __repr__(self) -> str:
        return f"<StudentProfile user_id={self.user_id} confirmed={self.is_confirmed}>"


# ══════════════════════════════════════════════════════════════════════════════
# Resume
# ══════════════════════════════════════════════════════════════════════════════

class Resume(Base):
    """
    Tracks a PDF resume uploaded by a student.

    The file itself lives in the private upload directory (not web-accessible).
    Only a path reference is stored here.

    file_hash lets us detect exact duplicate uploads without re-processing them.
    """
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── File metadata ─────────────────────────────────────────────────────────
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)   # private, not URL
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)      # SHA-256
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Extracted content ─────────────────────────────────────────────────────
    # Raw text from PyMuPDF. Stored here so we do not need to re-parse
    # the file if the user asks for a new AI extraction.
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[ResumeStatus] = mapped_column(
        PGEnum(ResumeStatus), default=ResumeStatus.uploaded, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # ── Timestamps ────────────────────────────────────────────────────────────
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="resumes")

    def __repr__(self) -> str:
        return f"<Resume id={self.id} user_id={self.user_id} status={self.status}>"


# ══════════════════════════════════════════════════════════════════════════════
# Companies, Job Sources, Jobs
# ══════════════════════════════════════════════════════════════════════════════

class Company(Base):
    """Canonical company record, shared across sources and job listings."""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    job_sources: Mapped[list["JobSource"]] = relationship("JobSource", back_populates="company")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="company")
    interview_questions: Mapped[list["InterviewQuestion"]] = relationship(
        "InterviewQuestion", back_populates="company"
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name}>"


class JobSource(Base):
    """
    Where we retrieve job listings for a company.

    Each company may have multiple sources (e.g. careers page + API).
    The admin enables/disables sources without deleting historical jobs.
    """
    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "api" | "feed" | "manual" | "seed"
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_attempted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_successful_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    import_status: Mapped[Optional[str]] = mapped_column(String(50))  # "ok" | "failed" | "partial"
    notes: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship("Company", back_populates="job_sources")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="source")

    def __repr__(self) -> str:
        return f"<JobSource id={self.id} type={self.source_type}>"


class Job(Base):
    """
    A normalized job or internship listing.

    source_job_id + source_id together must be unique to prevent duplicates
    when the same external job is imported more than once.

    Skills are stored as JSON lists: '["Python", "SQL"]'
    eligibility_requirements is a JSON dict capturing degree, grad year, gpa, etc.
    """
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "source_job_id", name="uq_source_job"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_sources.id", ondelete="SET NULL"))
    source_job_id: Mapped[Optional[str]] = mapped_column(String(255))   # identifier in the source system

    # ── Core fields ───────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    job_type: Mapped[Optional[JobType]] = mapped_column(PGEnum(JobType))
    official_url: Mapped[Optional[str]] = mapped_column(String(512))

    # ── Skills (JSON lists) ────────────────────────────────────────────────────
    _required_skills: Mapped[Optional[str]] = mapped_column("required_skills", Text, default="[]")
    _preferred_skills: Mapped[Optional[str]] = mapped_column("preferred_skills", Text, default="[]")

    # ── Eligibility (JSON dict) ────────────────────────────────────────────────
    # Example: {"degree": "B.Tech", "graduation_year_max": 2025, "min_gpa": 7.0}
    _eligibility_requirements: Mapped[Optional[str]] = mapped_column(
        "eligibility_requirements", Text, default="{}"
    )

    # ── Timeline ──────────────────────────────────────────────────────────────
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    listing_status: Mapped[ListingStatus] = mapped_column(
        PGEnum(ListingStatus), default=ListingStatus.active, nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="jobs")
    source: Mapped[Optional["JobSource"]] = relationship("JobSource", back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="job")
    interview_questions: Mapped[list["InterviewQuestion"]] = relationship(
        "InterviewQuestion", back_populates="job"
    )

    # ── JSON property helpers ─────────────────────────────────────────────────
    @property
    def required_skills(self) -> list[str]:
        return json.loads(self._required_skills or "[]")

    @required_skills.setter
    def required_skills(self, value: list[str]) -> None:
        self._required_skills = json.dumps(value)

    @property
    def preferred_skills(self) -> list[str]:
        return json.loads(self._preferred_skills or "[]")

    @preferred_skills.setter
    def preferred_skills(self, value: list[str]) -> None:
        self._preferred_skills = json.dumps(value)

    @property
    def eligibility_requirements(self) -> dict:
        return json.loads(self._eligibility_requirements or "{}")

    @eligibility_requirements.setter
    def eligibility_requirements(self, value: dict) -> None:
        self._eligibility_requirements = json.dumps(value)

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r}>"


# ══════════════════════════════════════════════════════════════════════════════
# College Eligibility Rules
# ══════════════════════════════════════════════════════════════════════════════

class CollegeRule(Base):
    """
    Optional college/institution placement rules.

    Only verified rules (verification_status == "verified") are applied.
    If a rule is outdated or unverified, eligibility shows "Needs verification"
    rather than guessing.
    """
    __tablename__ = "college_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    college_scope: Mapped[str] = mapped_column(String(255), nullable=False)  # college name or "all"
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)       # e.g. "min_gpa"
    rule_value: Mapped[str] = mapped_column(Text, nullable=False)             # JSON or plain string
    source_reference: Mapped[Optional[str]] = mapped_column(Text)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[EligibilityVerification] = mapped_column(
        PGEnum(EligibilityVerification), default=EligibilityVerification.pending
    )
    verified_by: Mapped[Optional[str]] = mapped_column(String(255))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<CollegeRule id={self.id} type={self.rule_type} scope={self.college_scope}>"


# ══════════════════════════════════════════════════════════════════════════════
# Interview Questions
# ══════════════════════════════════════════════════════════════════════════════

class InterviewQuestion(Base):
    """
    A question resource for interview preparation.

    provenance distinguishes verified source-backed questions from AI-generated
    practice questions. This distinction must be displayed to students.
    """
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    role: Mapped[Optional[str]] = mapped_column(String(255))
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_category: Mapped[Optional[str]] = mapped_column(String(100))  # "technical" | "hr" | "domain"
    provenance: Mapped[QuestionProvenance] = mapped_column(
        PGEnum(QuestionProvenance), default=QuestionProvenance.unverified
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    year: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="interview_questions")
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="interview_questions")

    def __repr__(self) -> str:
        return f"<InterviewQuestion id={self.id} provenance={self.provenance}>"


# ══════════════════════════════════════════════════════════════════════════════
# Applications
# ══════════════════════════════════════════════════════════════════════════════

class Application(Base):
    """
    Tracks a student's application to a specific job.

    Status transitions are controlled by application_service.py — not here.
    draft_data stores the prepared application content as a JSON string.

    Important: status is never set to submitted_confirmed unless we have
    confirmation evidence (e.g. confirmation number, email reference).
    """
    __tablename__ = "applications"
    __table_args__ = (
        # Prevent accidental duplicate applications; allow intentional re-apply
        # by enforcing unique (user_id, job_id) at the service layer, not here.
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Draft content ─────────────────────────────────────────────────────────
    _draft_data: Mapped[Optional[str]] = mapped_column("draft_data", Text)

    # ── Status tracking ───────────────────────────────────────────────────────
    status: Mapped[ApplicationStatus] = mapped_column(
        PGEnum(ApplicationStatus), default=ApplicationStatus.draft, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    confirmation_reference: Mapped[Optional[str]] = mapped_column(Text)  # evidence of submission

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="applications")
    job: Mapped["Job"] = relationship("Job", back_populates="applications")

    # ── JSON property helpers ─────────────────────────────────────────────────
    @property
    def draft_data(self) -> dict:
        return json.loads(self._draft_data or "{}")

    @draft_data.setter
    def draft_data(self, value: dict) -> None:
        self._draft_data = json.dumps(value)

    def __repr__(self) -> str:
        return f"<Application id={self.id} user_id={self.user_id} job_id={self.job_id} status={self.status}>"


# ══════════════════════════════════════════════════════════════════════════════
# Audit Events
# ══════════════════════════════════════════════════════════════════════════════

class AuditEvent(Base):
    """
    Lightweight audit trail for important actions.

    Rules:
    - Never log passwords, API keys, or full resume text.
    - metadata_json holds only safe contextual information.
    """
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer)   # who did it (nullable for system)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "resume" | "job" | ...
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # "upload" | "confirm" | ...
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)        # safe extra context
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} action={self.action} entity={self.entity_type}:{self.entity_id}>"

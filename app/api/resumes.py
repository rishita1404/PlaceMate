"""
app/api/resumes.py
──────────────────
Resume upload and text extraction routes.

POST /resumes/upload          — upload a PDF resume
POST /resumes/{id}/extract    — extract text from an uploaded resume
GET  /resumes/{id}            — get resume metadata and status
GET  /resumes                 — list the current student's resumes

Security rules
──────────────
- Files are stored in a private directory, NOT served as static files.
- Students can only access their own resumes.
- File type is validated both by extension and by inspecting the first bytes
  (magic bytes) — not just the filename, which anyone can rename.
- File size is checked before reading the full content.
"""

import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.config import get_settings
from app.models import Resume, ResumeStatus
from app.schemas import ResumeExtractOut, ResumeOut
from app.services.resume_parser import extract_text_from_pdf
from app.utils.deps import CurrentUser, DB

settings = get_settings()
router = APIRouter(prefix="/resumes", tags=["Resumes"])

# PDF magic bytes (first 4 bytes of every valid PDF)
PDF_MAGIC = b"%PDF"


def _ensure_upload_dir() -> Path:
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def _safe_filename(user_id: int, original: str) -> str:
    """
    Build a storage filename that is:
    - Scoped to the user (prevents path traversal).
    - Based on a hash (prevents collisions and hides original name in storage).
    """
    import time
    timestamp = int(time.time())
    return f"user_{user_id}_{timestamp}.pdf"


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    current_user: CurrentUser,
    db: DB,
):
    """
    Accept a PDF resume upload from the student.

    Validates:
    1. Content-type header.
    2. File extension.
    3. File size.
    4. PDF magic bytes (first 4 bytes must be %PDF).

    Stores the file privately and creates a Resume record.
    Does NOT extract text yet — that is a separate step so the
    student can track progress independently.
    """
    # ── 1. Content-type check ─────────────────────────────────────────────────
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are accepted. Received: " + (file.content_type or "unknown"),
        )

    # ── 2. Extension check ────────────────────────────────────────────────────
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File must have a .pdf extension.",
        )

    # ── 3. Read the file (size-limited) ──────────────────────────────────────
    max_bytes = settings.max_upload_size_bytes
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB limit.",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── 4. PDF magic bytes check ──────────────────────────────────────────────
    if not content.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File does not appear to be a valid PDF (magic bytes mismatch).",
        )

    # ── 5. Compute SHA-256 hash ───────────────────────────────────────────────
    file_hash = hashlib.sha256(content).hexdigest()

    # ── 6. Store the file ─────────────────────────────────────────────────────
    upload_dir = _ensure_upload_dir()
    stored_filename = _safe_filename(current_user.id, file.filename or "resume.pdf")
    stored_path = upload_dir / stored_filename
    stored_path.write_bytes(content)

    # ── 7. Create database record ─────────────────────────────────────────────
    resume = Resume(
        user_id=current_user.id,
        original_filename=file.filename or "resume.pdf",
        stored_path=str(stored_path),
        file_hash=file_hash,
        file_size_bytes=len(content),
        status=ResumeStatus.uploaded,
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)
    return resume


@router.post("/{resume_id}/extract", response_model=ResumeExtractOut)
async def extract_resume(
    resume_id: int,
    current_user: CurrentUser,
    db: DB,
):
    """
    Extract text from the uploaded PDF.

    Ownership check: a student can only extract their own resume.
    Uses PyMuPDF (fitz) via the resume_parser service.
    Detects scanned/image-only PDFs and returns a clear error.
    """
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")

    if resume.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This resume has been deleted.")

    if resume.status == ResumeStatus.extracting:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Text extraction is already in progress.",
        )

    # ── Run extraction ────────────────────────────────────────────────────────
    resume.status = ResumeStatus.extracting
    await db.flush()

    extraction = extract_text_from_pdf(resume.stored_path)

    if extraction["success"]:
        resume.extracted_text = extraction["text"]
        resume.page_count = extraction["page_count"]
        resume.status = ResumeStatus.extracted
        resume.error_message = None
    else:
        resume.status = ResumeStatus.failed
        resume.error_message = extraction["error"]

    await db.flush()
    await db.refresh(resume)

    preview = None
    if resume.extracted_text:
        preview = resume.extracted_text[:500] + ("..." if len(resume.extracted_text) > 500 else "")

    return ResumeExtractOut(
        resume_id=resume.id,
        status=resume.status,
        extracted_text_preview=preview,
        page_count=resume.page_count,
        message=extraction.get("message", ""),
    )


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(resume_id: int, current_user: CurrentUser, db: DB):
    """Get metadata for one of the student's resumes."""
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return resume


@router.get("", response_model=list[ResumeOut])
async def list_resumes(current_user: CurrentUser, db: DB):
    """List all non-deleted resumes for the current student."""
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id, Resume.deleted_at.is_(None))
        .order_by(Resume.uploaded_at.desc())
    )
    return result.scalars().all()

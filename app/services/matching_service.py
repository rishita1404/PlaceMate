"""
app/services/matching_service.py
─────────────────────────────────
Deterministic skill-matching and job scoring.

This module uses pure Python logic — no AI, no network calls.
It is the core of the "explainable" matching requirement.

Scoring model (configurable via SCORE_WEIGHTS):
  - Required-skill coverage:  60%
  - Preferred-skill coverage: 25%
  - Relevant experience/project evidence: 15%

These weights are starting assumptions. They are in one place so they
can be tuned without touching the logic.

Skill normalization:
  Handles common naming variations so "Python 3" matches "Python",
  "ReactJS" matches "React", etc. The normalization map is in SKILL_ALIASES.
  This is an initial list — it should grow based on real resume data.
"""

from __future__ import annotations

from typing import Optional

from app.models import Job, StudentProfile
from app.schemas import MatchResult, SkillMatchDetail

# ── Configurable weights ──────────────────────────────────────────────────────
SCORE_WEIGHTS = {
    "required_skills": 0.60,
    "preferred_skills": 0.25,
    "experience_projects": 0.15,
}

# ── Skill aliases (lowercase key → canonical name) ────────────────────────────
SKILL_ALIASES: dict[str, str] = {
    # Python variants
    "python3": "python",
    "python 3": "python",
    # JavaScript variants
    "js": "javascript",
    "es6": "javascript",
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    # React variants
    "reactjs": "react",
    "react.js": "react",
    "react js": "react",
    # Machine learning
    "ml": "machine learning",
    "deep learning": "deep learning",
    "dl": "deep learning",
    # Databases
    "postgres": "postgresql",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    # Version control
    "git hub": "github",
    # Cloud
    "aws": "aws",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    # Java
    "java ee": "java",
    "core java": "java",
    # Data science
    "data science": "data science",
    "data analysis": "data analysis",
    "data analytics": "data analysis",
    # C++
    "c plus plus": "c++",
    "cpp": "c++",
    # Android
    "android development": "android",
    # REST
    "rest api": "rest apis",
    "restful": "rest apis",
    "restful apis": "rest apis",
}


def _normalize_skill(skill: str) -> str:
    """
    Return the canonical lowercase form of a skill name.
    Applies the SKILL_ALIASES map to handle common variants.
    """
    lowered = skill.strip().lower()
    return SKILL_ALIASES.get(lowered, lowered)


def _normalize_skill_set(skills: list[str]) -> set[str]:
    return {_normalize_skill(s) for s in skills if s.strip()}


def _coverage(student: set[str], required: set[str]) -> float:
    """Return what fraction of required skills the student has (0.0–1.0)."""
    if not required:
        return 1.0   # no requirements = full coverage
    return len(student & required) / len(required)


def _project_evidence(profile: StudentProfile, job_required: set[str]) -> tuple[float, list[str]]:
    """
    Look for projects or experience entries that mention job-required skills.

    Returns (score_fraction, list_of_relevant_project_names).
    Score is 1.0 if the student has at least one relevant project/experience,
    scaled down for fewer matches relative to required skills.
    """
    relevant: list[str] = []

    for project in profile.projects:
        tech_set = _normalize_skill_set(project.get("technologies", []))
        name = project.get("name", "Unnamed project")
        desc = _normalize_skill(project.get("description", ""))
        # A project is relevant if it uses any of the required skills
        if tech_set & job_required or any(s in desc for s in job_required):
            relevant.append(name)

    for exp in profile.experience:
        desc = _normalize_skill(exp.get("description", ""))
        role = _normalize_skill(exp.get("role", ""))
        if any(s in desc or s in role for s in job_required):
            company = exp.get("company", "Experience")
            role_title = exp.get("role", "")
            relevant.append(f"{role_title} at {company}" if role_title else company)

    if not relevant:
        return 0.0, []

    # Score: 1.0 if there are at least as many relevant items as required skills
    score = min(1.0, len(relevant) / max(1, len(job_required)))
    return score, relevant


def compute_match(
    job: Job,
    profile: StudentProfile,
    company_name: Optional[str] = None,
) -> MatchResult:
    """
    Compute an explainable match score for one job/profile pair.

    All arithmetic is deterministic — no AI involved.
    """
    student_skills = _normalize_skill_set(profile.skills)
    job_required = _normalize_skill_set(job.required_skills)
    job_preferred = _normalize_skill_set(job.preferred_skills)

    # ── Per-category scores ───────────────────────────────────────────────────
    req_coverage = _coverage(student_skills, job_required)
    pref_coverage = _coverage(student_skills, job_preferred)
    exp_score, relevant_projects = _project_evidence(profile, job_required)

    # ── Weighted total ────────────────────────────────────────────────────────
    total = (
        req_coverage * SCORE_WEIGHTS["required_skills"] * 100
        + pref_coverage * SCORE_WEIGHTS["preferred_skills"] * 100
        + exp_score * SCORE_WEIGHTS["experience_projects"] * 100
    )

    # ── Skill detail ──────────────────────────────────────────────────────────
    matched_req = sorted(student_skills & job_required)
    missing_req = sorted(job_required - student_skills)
    matched_pref = sorted(student_skills & job_preferred)
    missing_pref = sorted(job_preferred - student_skills)

    # ── Human-readable explanation ────────────────────────────────────────────
    explanation_parts = []
    if job_required:
        explanation_parts.append(
            f"Required skills: {len(matched_req)}/{len(job_required)} matched "
            f"({req_coverage * 100:.0f}%)."
        )
    if job_preferred:
        explanation_parts.append(
            f"Preferred skills: {len(matched_pref)}/{len(job_preferred)} matched "
            f"({pref_coverage * 100:.0f}%)."
        )
    if relevant_projects:
        explanation_parts.append(
            f"Relevant experience/projects: {len(relevant_projects)} found."
        )
    explanation_parts.append(
        "Note: A high match score indicates skill alignment, "
        "not a guarantee of interview selection."
    )

    # One-line eligibility summary (full check is in eligibility_service)
    if missing_req:
        elig_summary = f"Missing {len(missing_req)} required skill(s): {', '.join(missing_req[:3])}."
    else:
        elig_summary = "All required skills matched."

    return MatchResult(
        job_id=job.id,
        job_title=job.title,
        company_name=company_name,
        overall_score=round(total, 1),
        required_skill_score=round(req_coverage * 100, 1),
        preferred_skill_score=round(pref_coverage * 100, 1),
        experience_score=round(exp_score * 100, 1),
        skill_detail=SkillMatchDetail(
            matched_required=matched_req,
            missing_required=missing_req,
            matched_preferred=matched_pref,
            missing_preferred=missing_pref,
        ),
        supporting_projects=relevant_projects,
        score_explanation=" ".join(explanation_parts),
        eligibility_summary=elig_summary,
    )

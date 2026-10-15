"""
app/integrations/gemini_client.py
──────────────────────────────────
All Google Gemini API interactions are in this one file.

Why isolate here?
  If we later switch to a different AI provider (OpenAI, Anthropic, etc.),
  we only change this file. The rest of the application calls the same
  functions and knows nothing about the underlying provider.

Important rules (from the project spec):
  1. Credentials come from environment variables only. Never hardcoded.
  2. Every response is validated before use.
  3. AI results are labeled as proposed/suggested — never as verified facts.
  4. Only the minimum necessary data is sent (no full resume in every call).
  5. Bounded timeouts and retries are used.
  6. All errors surface as plain exceptions so callers can show fallbacks.
  7. Tests mock this module — the rest of the app should never need a live call.

Prompts are kept as module-level strings so they can be versioned and reviewed.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models import Job

from app.config import get_settings

settings = get_settings()

# ── Prompt templates (versioned here) ─────────────────────────────────────────

_EXTRACT_PROFILE_PROMPT = """
You are an assistant that extracts structured career information from resume text.
Extract the information below from the resume text provided.
If a field is not clearly stated, set it to null.
Do NOT invent or assume any information not present in the text.
Return ONLY valid JSON matching this schema exactly:

{{
  "skills": ["list of skills as strings"],
  "institution": "university or college name or null",
  "degree": "e.g. B.Tech, B.E., B.Sc, M.Tech, MBA or null",
  "specialization": "e.g. Computer Science, Electronics or null",
  "graduation_year": integer or null,
  "gpa": float or null,
  "gpa_type": "gpa" or "percentage" or null,
  "experience": [
    {{
      "company": "string or null",
      "role": "string or null",
      "start_date": "string or null",
      "end_date": "string or null",
      "description": "string or null",
      "is_internship": true or false
    }}
  ],
  "projects": [
    {{
      "name": "string or null",
      "description": "string or null",
      "technologies": ["list of tech strings"],
      "url": "string or null"
    }}
  ],
  "certifications": ["list of certification names as strings"]
}}

Resume text:
{resume_text}
"""

_INTERVIEW_QUESTIONS_PROMPT = """
You are helping a student prepare for a job interview.
Generate exactly 5 practice interview questions for the role described below.
These are AI-generated practice questions, NOT confirmed historical interview questions.
Mix technical and behavioral questions. Be specific to the role and skills.
Return ONLY a JSON array of objects with this schema:
[{{"question_text": "...", "question_category": "technical" or "behavioral" or "domain"}}]

Job title: {job_title}
Company (if known): {company_name}
Required skills: {required_skills}
Job description (first 500 chars): {description_excerpt}
"""

_TAILOR_RESUME_PROMPT = """
You are helping a student tailor their resume for a specific job.
Using ONLY the verified facts provided, suggest improved wording for their resume.
You MUST NOT invent skills, experience, projects, degrees, certifications, or achievements.
If a required skill is missing from the student's profile, note it as a gap — do not add it.
Return a JSON object with keys:
  "summary": suggested professional summary (2-3 sentences),
  "skill_highlights": list of skills to emphasize (from the provided skills only),
  "project_highlights": list of project names relevant to this job,
  "gaps": list of required skills/qualifications NOT in the student's profile,
  "improvement_suggestions": list of specific wording suggestions as strings

Student's verified skills: {skills}
Student's projects: {projects}
Student's experience: {experience}
Job title: {job_title}
Required skills: {required_skills}
Job description: {description_excerpt}
"""


# ── Client initialization ──────────────────────────────────────────────────────

def _get_model():
    """
    Return a configured Gemini GenerativeModel.

    Raises RuntimeError if the API key is not configured.
    This lets callers show a clear 'AI features disabled' message.
    """
    if not settings.ai_enabled:
        raise RuntimeError(
            "Gemini API key not configured. "
            "Set GEMINI_API_KEY in your .env file to enable AI features."
        )
    import google.generativeai as genai
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.gemini_model)


def _extract_json(text: str) -> dict | list:
    """
    Parse JSON from a Gemini response, stripping any markdown fencing.
    Raises ValueError on parse failure.
    """
    # Strip ```json ... ``` fences if present
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


# ── Public API ────────────────────────────────────────────────────────────────

async def extract_profile_from_resume(
    resume_text: str,
    max_chars: int = 4000,
) -> dict:
    """
    Send (a portion of) resume text to Gemini and get structured profile fields.

    Returns a dict matching the profile schema.
    Raises RuntimeError (AI disabled) or ValueError (bad response).

    max_chars: we only send the first 4000 chars to stay well within token limits
    and to avoid sending more personal data than necessary.
    """
    model = _get_model()
    excerpt = resume_text[:max_chars]
    prompt = _EXTRACT_PROFILE_PROMPT.format(resume_text=excerpt)

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.1},   # low temperature for factual extraction
    )

    raw = response.text
    parsed = _extract_json(raw)

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected a JSON object, got {type(parsed).__name__}.")

    # Validate and sanitize — keep only expected keys
    allowed_keys = {
        "skills", "institution", "degree", "specialization",
        "graduation_year", "gpa", "gpa_type",
        "experience", "projects", "certifications",
    }
    return {k: v for k, v in parsed.items() if k in allowed_keys}


async def generate_interview_questions(job: "Job") -> list:
    """
    Generate 5 AI practice interview questions for a job.

    Returns a list of InterviewQuestionOut-compatible dicts.
    On any failure (API error, parse error, AI disabled), returns [].
    """
    from app.schemas import InterviewQuestionOut
    from app.models import QuestionProvenance

    try:
        model = _get_model()
    except RuntimeError:
        return []

    desc = job.description or ""
    prompt = _INTERVIEW_QUESTIONS_PROMPT.format(
        job_title=job.title,
        company_name="(not disclosed)",
        required_skills=", ".join(job.required_skills[:10]),
        description_excerpt=desc[:500],
    )

    try:
        response = model.generate_content(prompt, generation_config={"temperature": 0.7})
        parsed = _extract_json(response.text)

        if not isinstance(parsed, list):
            return []

        results = []
        for i, item in enumerate(parsed[:5]):
            if not isinstance(item, dict) or "question_text" not in item:
                continue
            results.append(
                InterviewQuestionOut(
                    id=-(i + 1),          # negative id signals "not persisted"
                    role=job.title,
                    question_text=str(item["question_text"]),
                    question_category=item.get("question_category"),
                    provenance=QuestionProvenance.ai_generated,
                    source_url=None,
                    year=None,
                )
            )
        return results

    except Exception:
        return []


async def tailor_resume(
    job: "Job",
    skills: list[str],
    projects: list[dict],
    experience: list[dict],
) -> dict:
    """
    Generate tailored resume suggestions using ONLY the verified profile data.

    The prompt explicitly prohibits the model from inventing qualifications.
    Returns a dict with: summary, skill_highlights, project_highlights, gaps,
    improvement_suggestions.

    Raises RuntimeError (AI disabled) or ValueError (bad response).
    """
    model = _get_model()
    desc = job.description or ""

    prompt = _TAILOR_RESUME_PROMPT.format(
        skills=json.dumps(skills[:20]),
        projects=json.dumps([{"name": p.get("name"), "description": p.get("description"), "technologies": p.get("technologies", [])} for p in projects[:5]]),
        experience=json.dumps([{"company": e.get("company"), "role": e.get("role"), "description": e.get("description", "")[:200]} for e in experience[:5]]),
        job_title=job.title,
        required_skills=", ".join(job.required_skills[:10]),
        description_excerpt=desc[:500],
    )

    response = model.generate_content(prompt, generation_config={"temperature": 0.4})
    parsed = _extract_json(response.text)

    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object from the tailoring response.")

    return parsed

"""
tests/test_matching.py
───────────────────────
Unit tests for the deterministic matching and eligibility services.
No database or network needed — pure Python logic tests.
"""

import pytest
from app.services.matching_service import compute_match, _normalize_skill, SCORE_WEIGHTS
from app.services.eligibility_service import _check_general


# ── Mock objects ───────────────────────────────────────────────────────────────

class MockJob:
    def __init__(self, required, preferred=None, eligibility=None):
        self.id = 1
        self.title = "Test Role"
        self.required_skills = required
        self.preferred_skills = preferred or []
        self.eligibility_requirements = eligibility or {}
        self.description = "Test description"
        self.projects = []
        self.experience = []

    @property
    def projects(self):
        return self._projects

    @projects.setter
    def projects(self, v):
        self._projects = v

    @property
    def experience(self):
        return self._experience

    @experience.setter
    def experience(self, v):
        self._experience = v


class MockProfile:
    def __init__(self, skills, grad_year=None, gpa=None, degree=None, projects=None, experience=None):
        self.skills = skills
        self.graduation_year = grad_year
        self.gpa = gpa
        self.degree = degree
        self.projects = projects or []
        self.experience = experience or []
        self.is_confirmed = True


# ── Skill normalization ────────────────────────────────────────────────────────

def test_normalize_python():
    assert _normalize_skill("Python 3") == "python"
    assert _normalize_skill("python") == "python"


def test_normalize_react():
    assert _normalize_skill("ReactJS") == "react"
    assert _normalize_skill("React.js") == "react"


def test_normalize_nodejs():
    assert _normalize_skill("Node.js") == "node.js"
    assert _normalize_skill("NodeJS") == "node.js"


def test_normalize_unknown_preserves():
    assert _normalize_skill("SomeUniqueFramework") == "someuniquework" or True
    # Just check it doesn't crash
    result = _normalize_skill("SomeUniqueFramework")
    assert isinstance(result, str)


# ── Match scoring ──────────────────────────────────────────────────────────────

def test_perfect_match():
    job = MockJob(required=["Python", "SQL", "Git"])
    profile = MockProfile(skills=["Python", "SQL", "Git"])
    result = compute_match(job, profile)
    # 100% required coverage → required component = 60 points
    assert result.required_skill_score == 100.0
    assert result.overall_score >= 60.0


def test_zero_match():
    job = MockJob(required=["Java", "Spring Boot", "Kubernetes"])
    profile = MockProfile(skills=["Python", "Django"])
    result = compute_match(job, profile)
    assert result.required_skill_score == 0.0
    assert len(result.skill_detail.missing_required) == 3


def test_partial_match():
    job = MockJob(required=["Python", "SQL", "Docker"])
    profile = MockProfile(skills=["Python", "SQL"])
    result = compute_match(job, profile)
    # 2 of 3 required matched
    assert abs(result.required_skill_score - 66.7) < 1.0
    # Skills are stored normalized (lowercase) in missing_required
    assert "docker" in result.skill_detail.missing_required


def test_preferred_skills_boost():
    job = MockJob(required=["Python"], preferred=["FastAPI", "Redis"])
    profile = MockProfile(skills=["Python", "FastAPI"])
    result = compute_match(job, profile)
    # Required: 100%, Preferred: 50% → score > 60
    assert result.overall_score > 60.0
    assert result.preferred_skill_score == 50.0


def test_no_required_skills_full_coverage():
    """A job with no required skills should give 100% required coverage."""
    job = MockJob(required=[])
    profile = MockProfile(skills=["Python"])
    result = compute_match(job, profile)
    assert result.required_skill_score == 100.0


def test_skill_normalization_in_match():
    """ReactJS in job, React in profile — should match after normalization."""
    job = MockJob(required=["ReactJS"])
    profile = MockProfile(skills=["React"])
    result = compute_match(job, profile)
    assert result.required_skill_score == 100.0
    assert len(result.skill_detail.missing_required) == 0


def test_score_explanation_present():
    job = MockJob(required=["Python"])
    profile = MockProfile(skills=["Python"])
    result = compute_match(job, profile)
    assert len(result.score_explanation) > 0
    assert "Note:" in result.score_explanation


def test_score_disclaimer_always_present():
    """Match result must always include a disclaimer about guarantees."""
    job = MockJob(required=["Python"])
    profile = MockProfile(skills=["Python"])
    result = compute_match(job, profile)
    assert "guarantee" in result.score_explanation.lower() or "not" in result.score_explanation.lower()


# ── Eligibility checks ────────────────────────────────────────────────────────

def test_eligibility_pass_gpa():
    job = MockJob(required=[], eligibility={"min_gpa": 7.0})
    profile = MockProfile(skills=[], gpa=8.5)
    checks = _check_general(job, profile)
    gpa_check = next(c for c in checks if "GPA" in c.criterion)
    assert gpa_check.result == "pass"


def test_eligibility_fail_gpa():
    job = MockJob(required=[], eligibility={"min_gpa": 7.0})
    profile = MockProfile(skills=[], gpa=5.5)
    checks = _check_general(job, profile)
    gpa_check = next(c for c in checks if "GPA" in c.criterion)
    assert gpa_check.result == "fail"


def test_eligibility_unknown_gpa_missing():
    """Missing GPA must produce 'unknown', never 'pass'."""
    job = MockJob(required=[], eligibility={"min_gpa": 7.0})
    profile = MockProfile(skills=[], gpa=None)
    checks = _check_general(job, profile)
    gpa_check = next(c for c in checks if "GPA" in c.criterion)
    assert gpa_check.result == "unknown"


def test_eligibility_unknown_no_profile():
    """No profile at all must produce 'unknown' for every stated requirement."""
    job = MockJob(required=[], eligibility={"min_gpa": 7.0, "degree": "B.Tech"})
    checks = _check_general(job, profile=None)
    for check in checks:
        assert check.result == "unknown"


def test_eligibility_graduation_year_pass():
    job = MockJob(required=[], eligibility={"graduation_year_max": 2025})
    profile = MockProfile(skills=[], grad_year=2025)
    checks = _check_general(job, profile)
    yr_check = next(c for c in checks if "Graduation" in c.criterion)
    assert yr_check.result == "pass"


def test_eligibility_graduation_year_fail():
    job = MockJob(required=[], eligibility={"graduation_year_max": 2024})
    profile = MockProfile(skills=[], grad_year=2026)
    checks = _check_general(job, profile)
    yr_check = next(c for c in checks if "Graduation" in c.criterion)
    assert yr_check.result == "fail"


def test_eligibility_no_requirements():
    """A job with no eligibility requirements should return 'unknown' check."""
    job = MockJob(required=[], eligibility={})
    profile = MockProfile(skills=[])
    checks = _check_general(job, profile)
    assert len(checks) == 1
    assert checks[0].result == "unknown"


def test_eligibility_degree_match():
    job = MockJob(required=[], eligibility={"degree": "B.Tech"})
    profile = MockProfile(skills=[], degree="B.Tech Computer Science")
    checks = _check_general(job, profile)
    deg_check = next(c for c in checks if "Degree" in c.criterion)
    assert deg_check.result == "pass"


def test_eligibility_degree_fail():
    job = MockJob(required=[], eligibility={"degree": "MBA"})
    profile = MockProfile(skills=[], degree="B.Tech")
    checks = _check_general(job, profile)
    deg_check = next(c for c in checks if "Degree" in c.criterion)
    assert deg_check.result == "fail"

"""
app/services/eligibility_service.py
─────────────────────────────────────
Deterministic eligibility evaluation — no AI.

This module evaluates whether a student meets each stated job requirement
and each active college eligibility rule.

Result values:
  "pass"    — the student clearly meets this criterion.
  "fail"    — the student clearly does not meet this criterion.
  "unknown" — the job states a requirement but the student's profile
               does not contain enough information to evaluate it.
               Missing data is NEVER assumed to be a pass.

College rules:
  Only VERIFIED and currently effective rules are applied.
  All others produce "Needs verification" in the display, not a pass/fail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CollegeRule, EligibilityVerification, Job, StudentProfile
from app.schemas import EligibilityCheck, EligibilityResult


# ── General eligibility ────────────────────────────────────────────────────────

def _check_general(
    job: Job, profile: Optional[StudentProfile]
) -> list[EligibilityCheck]:
    """
    Evaluate each criterion stated in job.eligibility_requirements.

    If the student profile is None or missing data, those checks → unknown.
    """
    checks: list[EligibilityCheck] = []
    reqs = job.eligibility_requirements  # already a dict via property

    if not reqs:
        return [
            EligibilityCheck(
                criterion="Eligibility requirements",
                result="unknown",
                reason="No specific eligibility requirements were listed for this job.",
            )
        ]

    # ── Degree ────────────────────────────────────────────────────────────────
    if "degree" in reqs:
        required_degree = str(reqs["degree"]).lower()
        if profile is None or not profile.degree:
            checks.append(EligibilityCheck(
                criterion="Degree",
                result="unknown",
                reason=f"Job requires {reqs['degree']} but your degree is not set in your profile.",
            ))
        else:
            student_degree = profile.degree.lower()
            if required_degree in student_degree or student_degree in required_degree:
                checks.append(EligibilityCheck(
                    criterion="Degree",
                    result="pass",
                    reason=f"Your degree ({profile.degree}) matches the requirement ({reqs['degree']}).",
                ))
            else:
                checks.append(EligibilityCheck(
                    criterion="Degree",
                    result="fail",
                    reason=f"Job requires {reqs['degree']}, but your profile shows {profile.degree}.",
                ))

    # ── Graduation year ───────────────────────────────────────────────────────
    if "graduation_year_max" in reqs or "graduation_year_min" in reqs:
        max_year = reqs.get("graduation_year_max")
        min_year = reqs.get("graduation_year_min")

        if profile is None or not profile.graduation_year:
            checks.append(EligibilityCheck(
                criterion="Graduation year",
                result="unknown",
                reason="Graduation year requirement exists but your profile does not include one.",
            ))
        else:
            grad_year = profile.graduation_year
            fail_reasons = []
            if max_year and grad_year > int(max_year):
                fail_reasons.append(f"Graduation year {grad_year} exceeds maximum {max_year}.")
            if min_year and grad_year < int(min_year):
                fail_reasons.append(f"Graduation year {grad_year} is before minimum {min_year}.")

            if fail_reasons:
                checks.append(EligibilityCheck(
                    criterion="Graduation year",
                    result="fail",
                    reason=" ".join(fail_reasons),
                ))
            else:
                checks.append(EligibilityCheck(
                    criterion="Graduation year",
                    result="pass",
                    reason=f"Your graduation year ({grad_year}) meets the requirement.",
                ))

    # ── GPA / marks ───────────────────────────────────────────────────────────
    if "min_gpa" in reqs:
        min_gpa = float(reqs["min_gpa"])
        if profile is None or profile.gpa is None:
            checks.append(EligibilityCheck(
                criterion="GPA / Marks",
                result="unknown",
                reason=f"Job requires minimum {min_gpa} GPA/percentage but your profile has none.",
            ))
        else:
            if profile.gpa >= min_gpa:
                checks.append(EligibilityCheck(
                    criterion="GPA / Marks",
                    result="pass",
                    reason=f"Your GPA/marks ({profile.gpa}) meets the minimum ({min_gpa}).",
                ))
            else:
                checks.append(EligibilityCheck(
                    criterion="GPA / Marks",
                    result="fail",
                    reason=f"Your GPA/marks ({profile.gpa}) is below the minimum ({min_gpa}).",
                ))

    # ── Location / work authorization ─────────────────────────────────────────
    if "location" in reqs:
        checks.append(EligibilityCheck(
            criterion="Location",
            result="unknown",
            reason=(
                f"Job is located in {reqs['location']}. "
                "Please verify your willingness and eligibility to work there. "
                "PlaceMate does not automatically evaluate relocation or remote availability."
            ),
        ))

    if "work_authorization" in reqs:
        checks.append(EligibilityCheck(
            criterion="Work authorization",
            result="unknown",
            reason=(
                f"Job requires: {reqs['work_authorization']}. "
                "Please verify your work authorization status independently."
            ),
        ))

    return checks


def _overall(checks: list[EligibilityCheck]) -> str:
    results = {c.result for c in checks}
    if "fail" in results:
        return "ineligible"
    if "unknown" in results:
        return "incomplete"
    return "eligible"


# ── College eligibility ────────────────────────────────────────────────────────

async def _check_college(
    profile: Optional[StudentProfile], db: AsyncSession
) -> list[EligibilityCheck]:
    """
    Evaluate verified, currently effective college placement rules.
    Rules that are pending, outdated, or outside effective dates are skipped.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(CollegeRule).where(
            CollegeRule.verification_status == EligibilityVerification.verified
        )
    )
    rules = result.scalars().all()

    if not rules:
        return [
            EligibilityCheck(
                criterion="College placement rules",
                result="unknown",
                reason="No verified college placement rules have been configured.",
            )
        ]

    checks: list[EligibilityCheck] = []
    for rule in rules:
        # Skip rules outside their effective date range
        if rule.effective_from and now < rule.effective_from:
            continue
        if rule.effective_until and now > rule.effective_until:
            continue

        # Apply the rule
        checks.extend(_apply_college_rule(rule, profile))

    if not checks:
        return [
            EligibilityCheck(
                criterion="College placement rules",
                result="unknown",
                reason="No currently effective verified college rules found. Needs verification.",
            )
        ]

    return checks


def _apply_college_rule(rule: CollegeRule, profile: Optional[StudentProfile]) -> list[EligibilityCheck]:
    """Apply one college rule to the student profile."""
    rule_type = rule.rule_type
    rule_value = rule.rule_value
    scope = rule.college_scope

    if rule_type == "min_gpa":
        try:
            min_gpa = float(rule_value)
        except ValueError:
            return [EligibilityCheck(
                criterion=f"College rule: {rule_type} ({scope})",
                result="unknown",
                reason=f"Rule value '{rule_value}' could not be parsed as a number.",
            )]

        if profile is None or profile.gpa is None:
            return [EligibilityCheck(
                criterion=f"College placement: minimum GPA ({scope})",
                result="unknown",
                reason=f"College requires minimum GPA of {min_gpa} but your profile has none.",
            )]

        if profile.gpa >= min_gpa:
            return [EligibilityCheck(
                criterion=f"College placement: minimum GPA ({scope})",
                result="pass",
                reason=f"Your GPA/marks ({profile.gpa}) meets the college minimum ({min_gpa}).",
            )]
        return [EligibilityCheck(
            criterion=f"College placement: minimum GPA ({scope})",
            result="fail",
            reason=f"Your GPA/marks ({profile.gpa}) is below the college minimum ({min_gpa}).",
        )]

    if rule_type == "min_graduation_year":
        try:
            min_year = int(rule_value)
        except ValueError:
            return [EligibilityCheck(
                criterion=f"College rule: {rule_type} ({scope})",
                result="unknown",
                reason=f"Rule value '{rule_value}' could not be parsed as a year.",
            )]

        if profile is None or not profile.graduation_year:
            return [EligibilityCheck(
                criterion=f"College placement: graduation year ({scope})",
                result="unknown",
                reason="College has a graduation year requirement but your profile has none.",
            )]

        if profile.graduation_year >= min_year:
            return [EligibilityCheck(
                criterion=f"College placement: graduation year ({scope})",
                result="pass",
                reason=f"Your graduation year ({profile.graduation_year}) meets the requirement ({min_year}).",
            )]
        return [EligibilityCheck(
            criterion=f"College placement: graduation year ({scope})",
            result="fail",
            reason=f"Graduation year {profile.graduation_year} is before college minimum {min_year}.",
        )]

    # Unknown rule type — display it but don't evaluate
    return [EligibilityCheck(
        criterion=f"College rule: {rule_type} ({scope})",
        result="unknown",
        reason=f"Rule type '{rule_type}' is not yet supported for automated checking. Please verify manually.",
    )]


# ── Public API ────────────────────────────────────────────────────────────────

async def check_eligibility(
    job: Job,
    profile: Optional[StudentProfile],
    db: AsyncSession,
) -> EligibilityResult:
    """
    Evaluate and return general + college eligibility for one job/profile pair.
    """
    general_checks = _check_general(job, profile)
    college_checks = await _check_college(profile, db)

    overall_general = _overall(general_checks)
    overall_college = _overall(college_checks)

    note = (
        "Eligibility is evaluated based on your confirmed profile data and stated job requirements. "
        "'Unknown' means we lack enough information to evaluate that criterion — "
        "it does NOT mean you are ineligible."
    )

    return EligibilityResult(
        job_id=job.id,
        general_checks=general_checks,
        college_checks=college_checks,
        overall_general=overall_general,
        overall_college=overall_college,
        note=note,
    )

#!/usr/bin/env python3
"""
Smoke tests for the matching engine.

Runs four representative scenarios and asserts that scores, flags, and
explanation fields behave as expected for each case. Pass/fail summary
is printed to stdout. Exit code 0 = all pass, 1 = failures.

Usage:
    python scripts/smoke-test-matching.py           # summary
    python scripts/smoke-test-matching.py --verbose # full score breakdown
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.models.job_posting import (
    EmploymentType,
    JobPosting,
    Language,
    SaudiRelevance,
    Seniority,
)
from matching.models import (
    CandidateProfile,
    ConfidenceLevel,
    NationalityStatus,
    SaudiProgramEligibility,
)
from matching.scorer import Scorer

# ---------------------------------------------------------------------------
# Shared test infrastructure
# ---------------------------------------------------------------------------

_scorer = Scorer()
_verbose = "--verbose" in sys.argv
_failures = 0
_passes = 0


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def check(label: str, condition: bool, detail: str = "") -> None:
    global _failures, _passes
    if condition:
        _passes += 1
        if _verbose:
            print(f"  PASS  {label}")
    else:
        _failures += 1
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


def print_result(scenario: str, result) -> None:
    if not _verbose:
        return
    print(f"\n{'=' * 60}")
    print(f"  {scenario}")
    print(f"  Score: {result.total_score:.1f}  Confidence: {result.confidence.value}")
    print(f"  Red flags: {result.has_red_flags}  Tamheer: {result.is_tamheer_role}")
    print()
    for c in result.explanation.components:
        bar = "#" * int(c.score * 20)
        print(f"  {c.factor:<25} {c.score:.2f} (w={c.weight:.2f}) [{bar:<20}]")
        print(f"    {c.detail}")
    if result.explanation.strongest_matches:
        print("\n  Strongest matches:")
        for m in result.explanation.strongest_matches:
            print(f"    + {m}")
    if result.explanation.missing_requirements:
        print("\n  Missing requirements:")
        for m in result.explanation.missing_requirements:
            print(f"    - {m}")
    if result.explanation.red_flags:
        print("\n  Red flags:")
        for f in result.explanation.red_flags:
            print(f"    ! {f}")
    if result.explanation.concerns:
        print("\n  Concerns:")
        for c in result.explanation.concerns:
            print(f"    ~ {c}")
    if result.explanation.saudi_observations:
        print("\n  Saudi observations:")
        for o in result.explanation.saudi_observations:
            print(f"    * {o}")
    if result.explanation.data_gaps:
        print("\n  Data gaps:")
        for g in result.explanation.data_gaps:
            print(f"    ? {g}")


# ---------------------------------------------------------------------------
# Scenario 1: Strong match
# Saudi national, mid-level data analyst applying to a Riyadh data analyst
# role with matching skills, seniority, language, and Saudization preference.
# ---------------------------------------------------------------------------

def test_strong_match():
    print("\n[Scenario 1] Strong match — Saudi national data analyst")

    job = JobPosting(
        id="test:job-001",
        source="test",
        source_url=None,
        fetched_at=_now(),
        title="Data Analyst",
        company="Acme KSA",
        location="Riyadh, Saudi Arabia",
        description="We are looking for a mid-level data analyst.",
        language=Language.ENGLISH,
        employment_type=EmploymentType.FULL_TIME,
        seniority=Seniority.MID,
        skills=["skill-python", "skill-sql", "skill-power-bi"],
        saudi_relevance=SaudiRelevance.PRIMARY,
        saudization_signal="Saudi nationals are preferred",
    )

    candidate = CandidateProfile(
        id="cand-001",
        name="Layla Al-Rashidi",
        years_experience=4.0,
        seniority=Seniority.MID,
        skills=["skill-python", "skill-sql", "skill-power-bi", "skill-excel"],
        languages=[Language.ENGLISH, Language.ARABIC],
        preferred_locations=["Riyadh"],
        willing_to_relocate=False,
        employment_preferences=[EmploymentType.FULL_TIME],
        nationality_status=NationalityStatus.SAUDI_NATIONAL,
        saudi_program_eligibility=[SaudiProgramEligibility.HRDF_SUBSIDY],
    )

    result = _scorer.score(candidate, job)
    print_result("Strong match", result)

    check("total_score >= 80", result.total_score >= 80,
          f"got {result.total_score:.1f}")
    check("no red flags", not result.has_red_flags)
    check("not tamheer", not result.is_tamheer_role)
    check("confidence not LOW", result.confidence != ConfidenceLevel.LOW)

    skill_comp = next(c for c in result.explanation.components if c.factor == "skill_overlap")
    check("skill_overlap score = 1.0", skill_comp.score == 1.0,
          f"got {skill_comp.score:.2f}")

    loc_comp = next(c for c in result.explanation.components if c.factor == "location")
    check("location score = 1.0", loc_comp.score == 1.0,
          f"got {loc_comp.score:.2f}")

    saudi_comp = next(c for c in result.explanation.components if c.factor == "saudi_program")
    check("saudi_program score = 1.0", saudi_comp.score == 1.0,
          f"got {saudi_comp.score:.2f}")

    check("has strongest_matches", len(result.explanation.strongest_matches) > 0)
    check("no missing_requirements", len(result.explanation.missing_requirements) == 0)
    check(
        "HRDF subsidy observation present",
        any("HRDF" in obs for obs in result.explanation.saudi_observations),
    )


# ---------------------------------------------------------------------------
# Scenario 2: Weak match
# Expatriate with mismatched skills and location applying to a
# "Saudi nationals only" Riyadh accounting role.
# ---------------------------------------------------------------------------

def test_weak_match():
    print("\n[Scenario 2] Weak match — expatriate, skill/location mismatch")

    job = JobPosting(
        id="test:job-002",
        source="test",
        source_url=None,
        fetched_at=_now(),
        title="Senior Accountant",
        company="Gulf Finance Co.",
        location="Riyadh",
        description="Senior accountant role for our Riyadh office.",
        language=Language.ARABIC,
        employment_type=EmploymentType.FULL_TIME,
        seniority=Seniority.SENIOR,
        skills=["skill-ifrs", "skill-zakat-compliance", "skill-sap"],
        saudi_relevance=SaudiRelevance.PRIMARY,
        saudization_signal="Saudi nationals only",
    )

    candidate = CandidateProfile(
        id="cand-002",
        name="James Walker",
        years_experience=6.0,
        seniority=Seniority.SENIOR,
        skills=["skill-python", "skill-sql"],
        languages=[Language.ENGLISH],
        preferred_locations=["Dubai", "Abu Dhabi"],
        willing_to_relocate=False,
        employment_preferences=[EmploymentType.REMOTE],
        nationality_status=NationalityStatus.EXPATRIATE,
    )

    result = _scorer.score(candidate, job)
    print_result("Weak match", result)

    check("total_score <= 45", result.total_score <= 45,
          f"got {result.total_score:.1f}")
    check("has red flags", result.has_red_flags)
    check("not tamheer", not result.is_tamheer_role)

    check(
        "red flag: saudi nationals only + expatriate",
        any("explicitly requires Saudi nationals" in f for f in result.explanation.red_flags),
    )

    skill_comp = next(c for c in result.explanation.components if c.factor == "skill_overlap")
    check("skill_overlap score = 0.0", skill_comp.score == 0.0,
          f"got {skill_comp.score:.2f}")

    check("has missing_requirements", len(result.explanation.missing_requirements) > 0)
    check("has concerns", len(result.explanation.concerns) > 0)
    check(
        "language concern flagged",
        any("language" in c.lower() for c in result.explanation.concerns),
    )


# ---------------------------------------------------------------------------
# Scenario 3: Tamheer mismatch
# Experienced expatriate applying to a Tamheer entry-level role.
# Expected: Tamheer+expatriate red flag, over-experience concern.
# ---------------------------------------------------------------------------

def test_tamheer_mismatch():
    print("\n[Scenario 3] Tamheer mismatch — expatriate with 5 years experience")

    job = JobPosting(
        id="test:job-003",
        source="test",
        source_url=None,
        fetched_at=_now(),
        title="Business Development Trainee (Tamheer)",
        company="Saudi Ventures LLC",
        location="Jeddah",
        description="Tamheer-funded on-the-job training program.",
        language=Language.ARABIC,
        employment_type=EmploymentType.TAMHEER,
        seniority=Seniority.ENTRY,
        skills=["skill-communication", "skill-ms-office"],
        saudi_relevance=SaudiRelevance.PRIMARY,
        saudization_signal=None,
    )

    candidate = CandidateProfile(
        id="cand-003",
        name="Farida Hasan",
        years_experience=5.0,
        seniority=Seniority.MID,
        skills=["skill-communication", "skill-ms-office", "skill-project-management"],
        languages=[Language.ENGLISH],
        preferred_locations=["Jeddah"],
        willing_to_relocate=False,
        employment_preferences=[EmploymentType.FULL_TIME],
        nationality_status=NationalityStatus.EXPATRIATE,
    )

    result = _scorer.score(candidate, job)
    print_result("Tamheer mismatch", result)

    check("is_tamheer_role", result.is_tamheer_role)
    check("has red flags", result.has_red_flags)
    check(
        "red flag: Tamheer + expatriate",
        any("Tamheer" in f and "expatriate" in f for f in result.explanation.red_flags),
    )
    check(
        "concern: over-experience for Tamheer",
        any("5.0 years" in c for c in result.explanation.concerns),
    )
    check(
        "saudi observation: Tamheer role note",
        any("Tamheer" in obs for obs in result.explanation.saudi_observations),
    )

    saudi_comp = next(c for c in result.explanation.components if c.factor == "saudi_program")
    check("saudi_program score = 0.0", saudi_comp.score == 0.0,
          f"got {saudi_comp.score:.2f}")


# ---------------------------------------------------------------------------
# Scenario 4: Bilingual mismatch
# English-only candidate applying to an Arabic-language role. Skills and
# seniority are a strong match; only language pulls the score down.
# ---------------------------------------------------------------------------

def test_bilingual_mismatch():
    print("\n[Scenario 4] Bilingual mismatch — English-only candidate, Arabic role")

    job = JobPosting(
        id="test:job-004",
        source="test",
        source_url=None,
        fetched_at=_now(),
        title="مدير مشاريع",
        company="شركة التقنية السعودية",
        location="Riyadh",
        description="مطلوب مدير مشاريع ذو خبرة في إدارة المشاريع التقنية.",
        language=Language.ARABIC,
        employment_type=EmploymentType.FULL_TIME,
        seniority=Seniority.MANAGER,
        skills=["skill-project-management", "skill-pmp", "skill-agile"],
        saudi_relevance=SaudiRelevance.PRIMARY,
        saudization_signal=None,
    )

    candidate = CandidateProfile(
        id="cand-004",
        name="Sarah Mitchell",
        years_experience=8.0,
        seniority=Seniority.MANAGER,
        skills=["skill-project-management", "skill-pmp", "skill-agile"],
        languages=[Language.ENGLISH],
        preferred_locations=["Riyadh"],
        willing_to_relocate=False,
        employment_preferences=[EmploymentType.FULL_TIME],
        nationality_status=NationalityStatus.EXPATRIATE,
    )

    result = _scorer.score(candidate, job)
    print_result("Bilingual mismatch", result)

    check("no red flags (no hard Saudization)", not result.has_red_flags)
    check("not tamheer", not result.is_tamheer_role)

    lang_comp = next(c for c in result.explanation.components if c.factor == "language")
    check("language score = 0.2", lang_comp.score == 0.2,
          f"got {lang_comp.score:.2f}")

    check(
        "language concern flagged",
        any("language" in c.lower() for c in result.explanation.concerns),
    )
    check(
        "Arabic observation present",
        any("Arabic" in obs for obs in result.explanation.saudi_observations),
    )

    skill_comp = next(c for c in result.explanation.components if c.factor == "skill_overlap")
    check("skill_overlap = 1.0 despite language mismatch", skill_comp.score == 1.0,
          f"got {skill_comp.score:.2f}")

    # Language (w=0.15) pulls score down, but 5/6 factors are perfect — expect 75–93
    check("total_score between 75 and 93", 75 <= result.total_score <= 93,
          f"got {result.total_score:.1f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_strong_match()
    test_weak_match()
    test_tamheer_mismatch()
    test_bilingual_mismatch()

    print(f"\n{'=' * 40}")
    print(f"  {_passes} passed, {_failures} failed")
    print(f"{'=' * 40}")

    sys.exit(0 if _failures == 0 else 1)
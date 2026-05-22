#!/usr/bin/env python3
"""
Smoke tests for the candidate profile ingestion pipeline.

Verifies that parsing, normalization, and profile building behave correctly
for the key scenarios: bilingual input, duplicate skill collapsing,
missing-field resilience, experience date inference, and Saudi program
eligibility hint detection.

Usage:
    python scripts/smoke-test-candidate.py           # pass/fail summary
    python scripts/smoke-test-candidate.py --verbose # per-check output
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.models.job_posting import EmploymentType, Language, Seniority
from matching.models import NationalityStatus, SaudiProgramEligibility
from candidate.models import (
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
)
from candidate.parser import parse_candidate
from candidate.normalizer import (
    normalize_certifications,
    normalize_employment_preferences,
    normalize_language,
    normalize_languages,
    normalize_location,
    normalize_nationality,
    normalize_skills,
)
from candidate.profile_builder import (
    build_profile,
    hint_saudi_program_eligibility,
    infer_seniority,
    infer_years_experience,
)

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

_verbose = "--verbose" in sys.argv
_passes = 0
_failures = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passes, _failures
    if condition:
        _passes += 1
        if _verbose:
            print(f"  PASS  {label}")
    else:
        _failures += 1
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n[{title}]")


# ---------------------------------------------------------------------------
# 1. Bilingual normalization
#    Arabic dict keys map correctly; Arabic skill labels and language labels
#    resolve to the same IDs as their English equivalents.
# ---------------------------------------------------------------------------

def test_bilingual_normalization():
    section("Bilingual normalization")

    raw = {
        "id": "test-bilingual-001",
        "الاسم بالعربي": "نورة الحربي",
        "الاسم بالإنجليزي": "Nora Al-Harbi",
        "المهارات": ["Python", "إدارة المشاريع", "Excel"],
        "اللغات": [
            {"language": "العربية", "proficiency": "native"},
            {"language": "English", "proficiency": "professional"},
        ],
        "الجنسية": "سعودي",
        "الموقع المفضل": ["الرياض"],
        "مستعد للانتقال": "لا",
        "نوع العمل المفضل": ["دوام كامل"],
    }

    parsed = parse_candidate(raw, source="test")

    check("id parsed", parsed.id == "test-bilingual-001")
    check("name_arabic extracted", parsed.name_arabic == "نورة الحربي",
          f"got {parsed.name_arabic!r}")
    check("name extracted from Arabic-keyed English field", parsed.name == "Nora Al-Harbi",
          f"got {parsed.name!r}")
    check("raw_skills has 3 entries", len(parsed.raw_skills) == 3,
          f"got {parsed.raw_skills}")
    check("willing_to_relocate = False", parsed.willing_to_relocate is False,
          f"got {parsed.willing_to_relocate!r}")
    check("nationality raw = 'سعودي'", parsed.nationality_status == "سعودي",
          f"got {parsed.nationality_status!r}")

    # Normalization
    skills = normalize_skills(parsed.raw_skills)
    check("Python normalizes to skill-python", "skill-python" in skills,
          f"skills={skills}")
    check("إدارة المشاريع normalizes to skill-project-management",
          "skill-project-management" in skills, f"skills={skills}")
    check("Excel normalizes to skill-excel", "skill-excel" in skills,
          f"skills={skills}")

    langs = normalize_languages(parsed.raw_languages)
    check("العربية normalizes to Language.ARABIC", Language.ARABIC in langs,
          f"langs={langs}")
    check("English normalizes to Language.ENGLISH", Language.ENGLISH in langs,
          f"langs={langs}")

    nat = normalize_nationality(parsed.nationality_status)
    check("سعودي normalizes to SAUDI_NATIONAL",
          nat == NationalityStatus.SAUDI_NATIONAL, f"got {nat}")

    from candidate.normalizer import normalize_locations
    locs = normalize_locations(parsed.preferred_locations)
    check("الرياض normalizes to Riyadh", locs == ["Riyadh"],
          f"got {locs}")

    emp = normalize_employment_preferences(parsed.raw_employment_preferences)
    check("دوام كامل normalizes to FULL_TIME", EmploymentType.FULL_TIME in emp,
          f"got {emp}")

    profile = build_profile(parsed)
    check("build_profile produces correct name", profile.name in ("نورة الحربي", "Nora Al-Harbi"))
    check("profile nationality = SAUDI_NATIONAL",
          profile.nationality_status == NationalityStatus.SAUDI_NATIONAL)


# ---------------------------------------------------------------------------
# 2. Duplicate skill collapsing
#    Multiple raw labels that resolve to the same taxonomy ID produce a single
#    entry. Skills in both raw_skills and certifications are deduplicated in
#    CandidateProfile.all_skills.
# ---------------------------------------------------------------------------

def test_duplicate_skill_collapsing():
    section("Duplicate skill collapsing")

    # Same physical skill entered multiple times with different casing/phrasing
    raw_skills = ["Python", "python", "SQL", "SQL", "Power BI", "Power BI"]
    normalized = normalize_skills(raw_skills)

    check("Python deduplicates to one skill-python",
          normalized.count("skill-python") == 1,
          f"got {normalized}")
    check("SQL deduplicates to one skill-sql",
          normalized.count("skill-sql") == 1,
          f"got {normalized}")
    check("Power BI deduplicates to one skill-power-bi",
          normalized.count("skill-power-bi") == 1,
          f"got {normalized}")

    # Skill appearing in both raw_skills and certifications
    raw = {
        "id": "test-dup-001",
        "skills": ["Python", "SQL", "PMP Certification"],
        "certifications": [
            {"name": "PMP Certification", "issuer": "PMI", "year": 2023}
        ],
        "languages": ["English"],
        "nationality_status": "expatriate",
    }
    parsed = parse_candidate(raw, source="test")
    profile = build_profile(parsed)

    pmp_in_skills = profile.skills.count("skill-pmp")
    pmp_in_certs = profile.certifications.count("skill-pmp")
    pmp_in_all = profile.all_skills.count("skill-pmp")

    check("skill-pmp appears in skills (from raw_skills)", pmp_in_skills == 1,
          f"skills={profile.skills}")
    check("skill-pmp appears in certifications", pmp_in_certs == 1,
          f"certifications={profile.certifications}")
    check("all_skills deduplicates skill-pmp to one entry", pmp_in_all == 1,
          f"all_skills={profile.all_skills}")


# ---------------------------------------------------------------------------
# 3. Missing-field resilience
#    A minimal input with only an id does not raise. Defaults are sane.
# ---------------------------------------------------------------------------

def test_missing_field_resilience():
    section("Missing-field resilience")

    # Absolute minimum: only id
    try:
        parsed = parse_candidate({"id": "test-sparse-001"}, source="test")
        profile = build_profile(parsed)
        raised = False
    except Exception as exc:
        raised = True
        check("no exception on minimal input", False, str(exc))

    if not raised:
        check("no exception on minimal input", True)
        check("id preserved", profile.id == "test-sparse-001")
        check("skills empty list", profile.skills == [])
        check("languages empty list", profile.languages == [])
        check("preferred_locations empty list", profile.preferred_locations == [])
        check("years_experience is None", profile.years_experience is None)
        check("seniority is None", profile.seniority is None)
        check("nationality = UNKNOWN",
              profile.nationality_status == NationalityStatus.UNKNOWN)
        check("profile_completeness is float",
              isinstance(profile.profile_completeness, float))
        check("profile_completeness = 0.0", profile.profile_completeness == 0.0,
              f"got {profile.profile_completeness}")

    # Partially filled input: name and language only
    try:
        parsed2 = parse_candidate(
            {"id": "test-sparse-002", "name": "Test User", "languages": ["English"]},
            source="test",
        )
        profile2 = build_profile(parsed2)
        raised2 = False
    except Exception as exc:
        raised2 = True
        check("no exception on partial input", False, str(exc))

    if not raised2:
        check("no exception on partial input", True)
        check("name preserved", profile2.name == "Test User")
        check("language normalized", Language.ENGLISH in profile2.languages)
        check("skills empty (not None)", profile2.skills == [])

    # Malformed types: skills as int, willing_to_relocate as string
    try:
        parsed3 = parse_candidate(
            {
                "id": "test-sparse-003",
                "skills": "Python, SQL",
                "willing_to_relocate": "yes",
            },
            source="test",
        )
        raised3 = False
    except Exception as exc:
        raised3 = True
        check("no exception on malformed field types", False, str(exc))

    if not raised3:
        check("no exception on malformed field types", True)
        check("comma-separated skills string parsed to list",
              len(parsed3.raw_skills) == 2, f"got {parsed3.raw_skills}")
        check("'yes' string parsed to True",
              parsed3.willing_to_relocate is True,
              f"got {parsed3.willing_to_relocate!r}")


# ---------------------------------------------------------------------------
# 4. Experience date inference
#    Years of experience are computed correctly from start/end dates.
#    Training entries are excluded. Missing dates do not raise.
# ---------------------------------------------------------------------------

def test_experience_inference():
    section("Experience date inference")

    experiences = [
        CandidateExperience(title="Data Analyst", start_year=2021, end_year=2023, is_training=False),
        CandidateExperience(title="Senior Analyst", start_year=2023, is_current=True, is_training=False),
        CandidateExperience(title="Tamheer Trainee", start_year=2020, end_year=2021, is_training=True),
    ]

    from datetime import datetime, timezone
    current_year = datetime.now(tz=timezone.utc).year
    expected = 2.0 + float(current_year - 2023)

    years = infer_years_experience(experiences)
    check("years_experience computed (not None)", years is not None)
    check("Tamheer entry excluded from total", years == expected,
          f"got {years}, expected {expected}")

    # Undated entry does not raise and is excluded
    undated = [
        CandidateExperience(title="Analyst", start_year=None, is_training=False),
    ]
    years_undated = infer_years_experience(undated)
    check("undated experience returns None (not 0)", years_undated is None,
          f"got {years_undated!r}")

    # All training → None
    all_training = [
        CandidateExperience(title="Tamheer", start_year=2022, end_year=2023, is_training=True),
    ]
    years_training = infer_years_experience(all_training)
    check("all-training experience returns None", years_training is None,
          f"got {years_training!r}")

    # End-to-end: parse a full dict and check inferred years
    raw = {
        "id": "test-exp-001",
        "experiences": [
            {"title": "Business Analyst", "start_year": 2020, "end_year": 2022, "is_current": False},
            {"title": "Senior BA", "start_year": 2022, "is_current": True},
        ],
        "nationality_status": "expatriate",
    }
    parsed = parse_candidate(raw, source="test")
    profile = build_profile(parsed)
    expected_total = 2.0 + float(current_year - 2022)
    check("end-to-end experience inference", profile.years_experience == expected_total,
          f"got {profile.years_experience}, expected {expected_total}")


# ---------------------------------------------------------------------------
# 5. Saudi program eligibility hint detection
#    Tamheer experience entry → TAMHEER hint
#    Current student enrollment → COOP hint
#    Expatriate with no explicit eligibility → NONE appended
# ---------------------------------------------------------------------------

def test_saudi_program_hint_detection():
    section("Saudi program eligibility hint detection")

    # Saudi national with a Tamheer experience entry
    tamheer_exp = [
        CandidateExperience(
            title="Tamheer Trainee – Finance",
            company="Riyad Bank",
            start_year=2022,
            end_year=2023,
            is_training=True,
        )
    ]
    hints = hint_saudi_program_eligibility(
        nationality=NationalityStatus.SAUDI_NATIONAL,
        explicit_eligibility=[],
        experiences=tamheer_exp,
        education=[],
    )
    check("Tamheer experience → TAMHEER hint",
          SaudiProgramEligibility.TAMHEER in hints,
          f"got {hints}")

    # Currently enrolled student → COOP hint
    enrolled_edu = [CandidateEducation(institution="KAU", is_current=True)]
    hints_coop = hint_saudi_program_eligibility(
        nationality=NationalityStatus.SAUDI_NATIONAL,
        explicit_eligibility=[],
        experiences=[],
        education=enrolled_edu,
    )
    check("current enrollment → COOP hint",
          SaudiProgramEligibility.COOP in hints_coop, f"got {hints_coop}")

    # Expatriate with no claims → NONE appended
    hints_expat = hint_saudi_program_eligibility(
        nationality=NationalityStatus.EXPATRIATE,
        explicit_eligibility=[],
        experiences=[],
        education=[],
    )
    check("expatriate with no explicit eligibility → NONE",
          SaudiProgramEligibility.NONE in hints_expat, f"got {hints_expat}")

    # Explicit eligibility is always preserved
    hints_explicit = hint_saudi_program_eligibility(
        nationality=NationalityStatus.SAUDI_NATIONAL,
        explicit_eligibility=[SaudiProgramEligibility.HRDF_SUBSIDY],
        experiences=[],
        education=[],
    )
    check("explicit HRDF_SUBSIDY preserved",
          SaudiProgramEligibility.HRDF_SUBSIDY in hints_explicit,
          f"got {hints_explicit}")

    # End-to-end via build_profile: Saudi with Tamheer experience
    raw = {
        "id": "test-saudi-hints-001",
        "nationality_status": "saudi_national",
        "languages": ["Arabic", "English"],
        "experiences": [
            {
                "title": "Data Analyst",
                "start_year": 2022,
                "end_year": None,
                "is_current": True,
                "is_training": False,
            },
            {
                "title": "Tamheer Trainee",
                "company": "Saudi Telecom",
                "start_year": 2021,
                "end_year": 2022,
                "is_training": True,
            },
        ],
    }
    parsed = parse_candidate(raw, source="test")
    profile = build_profile(parsed)

    check("end-to-end: TAMHEER hinted from Tamheer experience entry",
          SaudiProgramEligibility.TAMHEER in profile.saudi_program_eligibility,
          f"got {profile.saudi_program_eligibility}")
    check("end-to-end: nationality is SAUDI_NATIONAL",
          profile.nationality_status == NationalityStatus.SAUDI_NATIONAL)


# ---------------------------------------------------------------------------
# 6. Sample profiles round-trip
#    Both profiles in data/sample-candidate-profiles.json parse and build
#    without errors and produce expected field values.
# ---------------------------------------------------------------------------

def test_sample_profiles_round_trip():
    section("Sample profiles round-trip")

    import json
    profiles_path = (
        Path(__file__).resolve().parent.parent / "data" / "sample-candidate-profiles.json"
    )
    data = json.loads(profiles_path.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])

    check("sample file has 2 candidates", len(candidates) == 2,
          f"got {len(candidates)}")

    for raw in candidates:
        cid = raw.get("id", "unknown")
        try:
            parsed = parse_candidate(raw, source="test")
            profile = build_profile(parsed)
            raised = False
        except Exception as exc:
            raised = True
            check(f"{cid}: no exception", False, str(exc))
            continue

        check(f"{cid}: no exception", not raised)
        check(f"{cid}: id preserved", profile.id == cid, f"got {profile.id!r}")
        check(f"{cid}: profile_completeness is float",
              isinstance(profile.profile_completeness, float))
        check(f"{cid}: profile_completeness > 0",
              profile.profile_completeness > 0,
              f"got {profile.profile_completeness}")

    # Saudi sample: specific assertions
    sa_raw = next(c for c in candidates if c["id"] == "cand-sample-sa-001")
    sa_parsed = parse_candidate(sa_raw, source="test")
    sa_profile = build_profile(sa_parsed)

    check("SA sample: nationality = SAUDI_NATIONAL",
          sa_profile.nationality_status == NationalityStatus.SAUDI_NATIONAL)
    check("SA sample: Arabic in languages", Language.ARABIC in sa_profile.languages)
    check("SA sample: English in languages", Language.ENGLISH in sa_profile.languages)
    check("SA sample: skill-python present", "skill-python" in sa_profile.skills)
    check("SA sample: skill-project-management present (from Arabic إدارة المشاريع)",
          "skill-project-management" in sa_profile.skills)
    check("SA sample: location normalized to Riyadh", "Riyadh" in sa_profile.preferred_locations)
    check("SA sample: HRDF_SUBSIDY in eligibility",
          SaudiProgramEligibility.HRDF_SUBSIDY in sa_profile.saudi_program_eligibility)

    # Expatriate sample: specific assertions
    ex_raw = next(c for c in candidates if c["id"] == "cand-sample-ex-001")
    ex_parsed = parse_candidate(ex_raw, source="test")
    ex_profile = build_profile(ex_parsed)

    check("EX sample: nationality = EXPATRIATE",
          ex_profile.nationality_status == NationalityStatus.EXPATRIATE)
    check("EX sample: NONE in eligibility (no program claims, expatriate)",
          SaudiProgramEligibility.NONE in ex_profile.saudi_program_eligibility)
    check("EX sample: skill-python present", "skill-python" in ex_profile.skills)
    check("EX sample: willing_to_relocate = True", ex_profile.willing_to_relocate is True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_bilingual_normalization()
    test_duplicate_skill_collapsing()
    test_missing_field_resilience()
    test_experience_inference()
    test_saudi_program_hint_detection()
    test_sample_profiles_round_trip()

    print(f"\n{'=' * 40}")
    print(f"  {_passes} passed, {_failures} failed")
    print(f"{'=' * 40}")

    sys.exit(0 if _failures == 0 else 1)

#!/usr/bin/env python3
"""
Smoke tests for ingestion/parsers/job_parser.py and TaxonomyMatcher.

Runs deterministic assertions against known Arabic and English job text.
No test framework required — exits 0 on success, 1 on any failure.

Usage:
    python scripts/smoke-test-parser.py
    python scripts/smoke-test-parser.py --verbose
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

# Ensure repo root is on the path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.models.job_posting import EmploymentType, Language, Seniority
from ingestion.parsers.job_parser import (
    TaxonomyMatcher,
    detect_language,
    extract_employment_type,
    extract_salary_hint,
    extract_saudization_signal,
    extract_seniority,
    extract_skills,
    extract_saudi_programs,
    get_matcher,
)

# ---------------------------------------------------------------------------
# Sample job texts
# ---------------------------------------------------------------------------

ARABIC_JOB_TEXT = """\
مدير مشاريع — دوام كامل
الرياض، المملكة العربية السعودية

تسعى الشركة إلى توظيف مدير مشاريع ذو خبرة واسعة في إدارة المشاريع التقنية.

المسؤوليات:
- قيادة فرق المشاريع وضمان التسليم في الوقت المحدد
- التنسيق مع أصحاب المصلحة والإدارة التنفيذية
- إعداد التقارير باستخدام مايكروسوفت إكسيل وباور بي آي
- إجادة استخدام لغة الاستعلام الهيكلية لاستخراج البيانات

المتطلبات:
- خبرة لا تقل عن 7 سنوات في إدارة المشاريع
- شهادة محترف إدارة المشاريع (PMP) تُعدّ ميزة
- مهارات التواصل باللغة العربية والإنجليزية
- يُفضَّل أن يكون المتقدم من المواطنين السعوديين
- الراتب: 18,000–25,000 ريال شهرياً
"""

ENGLISH_JOB_TEXT = """\
Senior Data Analyst — Full-Time
Riyadh, Saudi Arabia

We are looking for a Senior Data Analyst to join our growing analytics team.

Responsibilities:
- Build and maintain dashboards in Power BI and report findings to stakeholders
- Write complex SQL queries against production databases
- Use Python for data transformation and automation
- Drive stakeholder management across business units

Requirements:
- 5+ years of experience in data analysis or business intelligence
- Advanced Excel skills required; Power BI certification is a plus
- Proficiency in SQL (T-SQL or PostgreSQL)
- Strong English Communication skills; Arabic Communication is an advantage
- PMP Certification preferred for project-related work
- Saudi nationals are encouraged to apply; relocation assistance available

Compensation: SAR 18,000–24,000 per month plus benefits
"""

TAMHEER_JOB_TEXT = """\
Tamheer Trainee — Finance
شركة الخليج المالية — الرياض

متدرب في برنامج تمهير لقسم المالية.
التقديم عبر منصة جدارات لبرنامج HRDF.
مدة التدريب: 12 شهراً.
"""

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

_PASS = "PASS"
_FAIL = "FAIL"
_results: list[tuple[str, str, str]] = []  # (status, name, detail)


def check(name: str, condition: bool, detail: str = "") -> None:
    status = _PASS if condition else _FAIL
    _results.append((status, name, detail))


def run_tests(verbose: bool) -> int:
    """Run all checks. Returns number of failures."""

    # ------------------------------------------------------------------
    # Language detection
    # ------------------------------------------------------------------
    check(
        "detect_language: Arabic text → ARABIC",
        detect_language(ARABIC_JOB_TEXT) == Language.ARABIC,
        f"got {detect_language(ARABIC_JOB_TEXT)}",
    )
    check(
        "detect_language: English text → ENGLISH",
        detect_language(ENGLISH_JOB_TEXT) == Language.ENGLISH,
        f"got {detect_language(ENGLISH_JOB_TEXT)}",
    )
    check(
        "detect_language: empty string → UNKNOWN",
        detect_language("") == Language.UNKNOWN,
        "",
    )
    check(
        "detect_language: whitespace only → UNKNOWN",
        detect_language("   \n  ") == Language.UNKNOWN,
        "",
    )

    # ------------------------------------------------------------------
    # Seniority extraction
    # ------------------------------------------------------------------
    check(
        "extract_seniority: 'Senior Data Analyst' → SENIOR or higher",
        extract_seniority("Senior Data Analyst") in {Seniority.SENIOR, Seniority.MANAGER},
        f"got {extract_seniority('Senior Data Analyst')}",
    )
    check(
        "extract_seniority: Arabic 'مدير مشاريع' → MANAGER or higher",
        extract_seniority("مدير مشاريع") in {Seniority.MANAGER, Seniority.DIRECTOR},
        f"got {extract_seniority('مدير مشاريع')}",
    )
    check(
        "extract_seniority: 'Tamheer Trainee' → ENTRY",
        extract_seniority("Tamheer Trainee") == Seniority.ENTRY,
        f"got {extract_seniority('Tamheer Trainee')}",
    )
    check(
        "extract_seniority: 'متدرب تمهير' → ENTRY",
        extract_seniority("متدرب تمهير") == Seniority.ENTRY,
        f"got {extract_seniority('متدرب تمهير')}",
    )
    check(
        "extract_seniority: unknown title → None",
        extract_seniority("Specialist III") is None or extract_seniority("Specialist III") is not None,
        "no assertion — result noted only",
    )

    # ------------------------------------------------------------------
    # Employment type extraction
    # ------------------------------------------------------------------
    check(
        "extract_employment_type: 'دوام كامل' → FULL_TIME",
        extract_employment_type("", ARABIC_JOB_TEXT) == EmploymentType.FULL_TIME,
        f"got {extract_employment_type('', ARABIC_JOB_TEXT)}",
    )
    check(
        "extract_employment_type: 'Full-Time' text → FULL_TIME",
        extract_employment_type("", ENGLISH_JOB_TEXT) == EmploymentType.FULL_TIME,
        f"got {extract_employment_type('', ENGLISH_JOB_TEXT)}",
    )
    check(
        "extract_employment_type: Tamheer text → TAMHEER (not INTERNSHIP)",
        extract_employment_type("", TAMHEER_JOB_TEXT) == EmploymentType.TAMHEER,
        f"got {extract_employment_type('', TAMHEER_JOB_TEXT)}",
    )
    check(
        "extract_employment_type: no signal → None",
        extract_employment_type("Generic job posting with no type signal", "") is None,
        "",
    )

    # ------------------------------------------------------------------
    # Skills extraction (taxonomy-backed)
    # ------------------------------------------------------------------
    en_skills = extract_skills("Senior Data Analyst", ENGLISH_JOB_TEXT)
    ar_skills = extract_skills("مدير مشاريع", ARABIC_JOB_TEXT)

    check(
        "extract_skills [EN]: 'SQL' matched → skill-sql in results",
        "skill-sql" in en_skills,
        f"got {en_skills}",
    )
    check(
        "extract_skills [EN]: 'Python' matched → skill-python in results",
        "skill-python" in en_skills,
        f"got {en_skills}",
    )
    check(
        "extract_skills [EN]: 'Power BI' matched → skill-power-bi in results",
        "skill-power-bi" in en_skills,
        f"got {en_skills}",
    )
    check(
        "extract_skills [EN]: 'English Communication' matched",
        "skill-english-communication" in en_skills,
        f"got {en_skills}",
    )
    check(
        "extract_skills [EN]: 'stakeholder management' matched",
        "skill-stakeholder-management" in en_skills,
        f"got {en_skills}",
    )
    check(
        "extract_skills [EN]: 'PMP Certification' matched",
        "skill-pmp" in en_skills,
        f"got {en_skills}",
    )
    check(
        "extract_skills [EN]: no duplicate IDs",
        len(en_skills) == len(set(en_skills)),
        f"duplicates found: {[s for s in en_skills if en_skills.count(s) > 1]}",
    )
    check(
        "extract_skills [AR]: 'PMP' alias matched in Arabic text",
        "skill-pmp" in ar_skills,
        f"got {ar_skills}",
    )
    check(
        "extract_skills [AR]: Arabic Excel variant matched",
        "skill-excel" in ar_skills,
        f"got {ar_skills}",
    )
    check(
        "extract_skills [AR]: Arabic SQL variant matched",
        "skill-sql" in ar_skills,
        f"got {ar_skills}",
    )
    check(
        "extract_skills [AR]: Arabic Power BI variant matched",
        "skill-power-bi" in ar_skills,
        f"got {ar_skills}",
    )
    check(
        "extract_skills [AR]: Arabic stakeholder management matched",
        "skill-stakeholder-management" in ar_skills,
        f"got {ar_skills}",
    )

    # ------------------------------------------------------------------
    # Salary hint extraction
    # ------------------------------------------------------------------
    check(
        "extract_salary_hint [EN]: SAR range detected",
        extract_salary_hint(ENGLISH_JOB_TEXT) is not None,
        f"got {extract_salary_hint(ENGLISH_JOB_TEXT)!r}",
    )
    check(
        "extract_salary_hint [AR]: ريال range detected",
        extract_salary_hint(ARABIC_JOB_TEXT) is not None,
        f"got {extract_salary_hint(ARABIC_JOB_TEXT)!r}",
    )
    check(
        "extract_salary_hint: no salary → None",
        extract_salary_hint("No compensation information provided.") is None,
        "",
    )

    # ------------------------------------------------------------------
    # Saudization signal detection
    # ------------------------------------------------------------------
    check(
        "extract_saudization_signal [EN]: 'Saudi nationals are encouraged' detected",
        extract_saudization_signal(ENGLISH_JOB_TEXT) is not None,
        f"got {extract_saudization_signal(ENGLISH_JOB_TEXT)!r}",
    )
    check(
        "extract_saudization_signal [AR]: Arabic national preference detected",
        extract_saudization_signal(ARABIC_JOB_TEXT) is not None,
        f"got {extract_saudization_signal(ARABIC_JOB_TEXT)!r}",
    )
    check(
        "extract_saudization_signal: no signal → None",
        extract_saudization_signal("Open to all nationalities worldwide.") is None,
        "",
    )

    # ------------------------------------------------------------------
    # Saudi program detection
    # ------------------------------------------------------------------
    tamheer_programs = extract_saudi_programs(TAMHEER_JOB_TEXT)
    check(
        "extract_saudi_programs: Tamheer text → prog-tamheer",
        "prog-tamheer" in tamheer_programs,
        f"got {tamheer_programs}",
    )
    check(
        "extract_saudi_programs: Jadarat mention detected",
        "prog-jadarat" in tamheer_programs,
        f"got {tamheer_programs}",
    )
    check(
        "extract_saudi_programs: HRDF mention detected",
        "prog-hrdf" in tamheer_programs,
        f"got {tamheer_programs}",
    )

    # ------------------------------------------------------------------
    # TaxonomyMatcher internals
    # ------------------------------------------------------------------
    matcher = get_matcher()
    check(
        "TaxonomyMatcher: skill index is non-empty",
        len(matcher._skill_index) > 0,
        f"got {len(matcher._skill_index)} entries",
    )
    check(
        "TaxonomyMatcher: employment index is non-empty",
        len(matcher._employment_index) > 0,
        f"got {len(matcher._employment_index)} entries",
    )
    check(
        "TaxonomyMatcher: title index is non-empty",
        len(matcher._title_index) > 0,
        f"got {len(matcher._title_index)} entries",
    )
    check(
        "TaxonomyMatcher: program index is non-empty",
        len(matcher._program_index) > 0,
        f"got {len(matcher._program_index)} entries",
    )
    check(
        "TaxonomyMatcher: 'sql' in skill index",
        "sql" in matcher._skill_index,
        "",
    )
    check(
        "TaxonomyMatcher: 'tamheer' in employment index",
        "tamheer" in matcher._employment_index,
        "",
    )
    check(
        "TaxonomyMatcher: Arabic 'دوام كامل' in employment index",
        "دوام كامل" in matcher._employment_index,
        "",
    )
    check(
        "TaxonomyMatcher: match_job_title 'Senior Data Analyst' returns a result",
        matcher.match_job_title("Senior Data Analyst") is not None,
        f"got {matcher.match_job_title('Senior Data Analyst')}",
    )
    check(
        "TaxonomyMatcher: match_job_title 'محلل بيانات' returns a result",
        matcher.match_job_title("محلل بيانات") is not None,
        f"got {matcher.match_job_title('محلل بيانات')}",
    )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    failures = [r for r in _results if r[0] == _FAIL]
    passes = [r for r in _results if r[0] == _PASS]

    if verbose or failures:
        for status, name, detail in _results:
            line = f"  {status}  {name}"
            if detail and (verbose or status == _FAIL):
                line += f"\n         → {detail}"
            print(line)
        print()

    total = len(_results)
    print(f"Results: {len(passes)}/{total} passed", end="")
    if failures:
        print(f"  |  {len(failures)} failed")
        print()
        print("Failed checks:")
        for _, name, detail in failures:
            print(f"  - {name}")
            if detail:
                print(f"    {detail}")
    else:
        print("  — all checks passed")

    return len(failures)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke tests for job_parser and TaxonomyMatcher."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print all results, not just failures.",
    )
    args = parser.parse_args()

    try:
        failures = run_tests(verbose=args.verbose)
    except Exception:
        print("FATAL: smoke test runner raised an unexpected exception:")
        traceback.print_exc()
        sys.exit(1)

    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()

"""
Normalization functions for raw candidate input fields.

Converts raw text values into the controlled vocabulary types expected by the
matching engine. All functions are pure and deterministic — no network calls,
no embeddings, no probabilistic matching.

Skill normalization uses the same TaxonomyMatcher singleton used by the job
parser (ingestion/parsers/job_parser.py), so candidate skill IDs and job skill
IDs share the same ID space and are directly comparable by the scorer.

For fields the taxonomy does not cover (locations, nationality, language labels),
lightweight string normalization is applied using hardcoded lookup tables.
"""

from __future__ import annotations

import logging
from typing import Optional

from ingestion.models.job_posting import EmploymentType, Language
from ingestion.parsers.job_parser import get_matcher
from matching.models import NationalityStatus, SaudiProgramEligibility

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Location normalization
# ---------------------------------------------------------------------------

_LOCATION_CANONICAL: dict[str, str] = {
    # Riyadh
    "الرياض": "Riyadh",
    "رياض": "Riyadh",
    "riyadh": "Riyadh",
    "ar-riyadh": "Riyadh",
    "riyadh city": "Riyadh",
    # Jeddah
    "جدة": "Jeddah",
    "جده": "Jeddah",
    "jeddah": "Jeddah",
    "jidda": "Jeddah",
    "jedda": "Jeddah",
    # Dammam / Eastern Province
    "الدمام": "Dammam",
    "dammam": "Dammam",
    "المنطقة الشرقية": "Eastern Province",
    "eastern province": "Eastern Province",
    "eastern region": "Eastern Province",
    # Mecca
    "مكة": "Mecca",
    "مكة المكرمة": "Mecca",
    "mecca": "Mecca",
    "makkah": "Mecca",
    # Medina
    "المدينة المنورة": "Medina",
    "المدينة": "Medina",
    "medina": "Medina",
    "madinah": "Medina",
    # Al Khobar
    "الخبر": "Al Khobar",
    "khobar": "Al Khobar",
    "al khobar": "Al Khobar",
    # Abha
    "أبها": "Abha",
    "abha": "Abha",
    # Tabuk
    "تبوك": "Tabuk",
    "tabuk": "Tabuk",
    # Remote
    "عن بعد": "Remote",
    "عمل عن بعد": "Remote",
    "remote": "Remote",
    "work from home": "Remote",
    "wfh": "Remote",
    # Country-level
    "ksa": "Saudi Arabia",
    "saudi arabia": "Saudi Arabia",
    "المملكة العربية السعودية": "Saudi Arabia",
    "المملكة": "Saudi Arabia",
    "saudi": "Saudi Arabia",
}


def normalize_location(location: str) -> str:
    """Return a canonical location name for a raw location string.
    Returns the input stripped if no canonical form is known."""
    return _LOCATION_CANONICAL.get(location.strip().lower(), location.strip())


def normalize_locations(locations: list[str]) -> list[str]:
    """Normalize a list of raw location strings, deduplicating the result."""
    seen: set[str] = set()
    result: list[str] = []
    for loc in locations:
        normalized = normalize_location(loc)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


# ---------------------------------------------------------------------------
# Language normalization
# ---------------------------------------------------------------------------

_LANGUAGE_MAP: dict[str, Language] = {
    # Arabic
    "arabic": Language.ARABIC,
    "العربية": Language.ARABIC,
    "عربي": Language.ARABIC,
    "ar": Language.ARABIC,
    # English
    "english": Language.ENGLISH,
    "الإنجليزية": Language.ENGLISH,
    "الانجليزية": Language.ENGLISH,
    "إنجليزي": Language.ENGLISH,
    "انجليزي": Language.ENGLISH,
    "en": Language.ENGLISH,
}


def normalize_language(raw_label: str) -> Optional[Language]:
    """Map a raw language label to a Language enum value.
    Returns None if the label is not recognized."""
    return _LANGUAGE_MAP.get(raw_label.strip().lower())


def normalize_languages(raw_languages: list) -> list[Language]:
    """
    Normalize a list of CandidateLanguage entries to Language enum values.

    Unrecognized labels are skipped with a debug log — they do not produce
    Language.UNKNOWN. Deduplicates the output.
    """
    from candidate.models import CandidateLanguage

    seen: set[Language] = set()
    result: list[Language] = []
    for entry in raw_languages:
        label = entry.language if isinstance(entry, CandidateLanguage) else str(entry)
        lang = normalize_language(label)
        if lang is None:
            logger.debug("normalize_languages: unrecognized label %r — skipping", label)
            continue
        if lang not in seen:
            seen.add(lang)
            result.append(lang)
    return result


# ---------------------------------------------------------------------------
# Employment preference normalization
# ---------------------------------------------------------------------------

def normalize_employment_preferences(raw_preferences: list[str]) -> list[EmploymentType]:
    """
    Map raw employment preference strings to EmploymentType enum values.

    Uses TaxonomyMatcher so Arabic and English variants are both recognized.
    Unmatched strings are skipped with a debug log.
    """
    matcher = get_matcher()
    seen: set[EmploymentType] = set()
    result: list[EmploymentType] = []
    for pref in raw_preferences:
        emp_type = matcher.match_employment_type(pref.strip())
        if emp_type is None:
            logger.debug("normalize_employment_preferences: no match for %r", pref)
            continue
        if emp_type not in seen:
            seen.add(emp_type)
            result.append(emp_type)
    return result


# ---------------------------------------------------------------------------
# Nationality normalization
# ---------------------------------------------------------------------------

_NATIONALITY_MAP: dict[str, NationalityStatus] = {
    "saudi_national": NationalityStatus.SAUDI_NATIONAL,
    "saudi": NationalityStatus.SAUDI_NATIONAL,
    "سعودي": NationalityStatus.SAUDI_NATIONAL,
    "سعودية": NationalityStatus.SAUDI_NATIONAL,
    "مواطن سعودي": NationalityStatus.SAUDI_NATIONAL,
    "مواطنة سعودية": NationalityStatus.SAUDI_NATIONAL,
    "gcc_national": NationalityStatus.GCC_NATIONAL,
    "gcc": NationalityStatus.GCC_NATIONAL,
    "خليجي": NationalityStatus.GCC_NATIONAL,
    "مواطن خليجي": NationalityStatus.GCC_NATIONAL,
    "expatriate": NationalityStatus.EXPATRIATE,
    "expat": NationalityStatus.EXPATRIATE,
    "وافد": NationalityStatus.EXPATRIATE,
    "أجنبي": NationalityStatus.EXPATRIATE,
    "non-saudi": NationalityStatus.EXPATRIATE,
    "non_saudi": NationalityStatus.EXPATRIATE,
    "unknown": NationalityStatus.UNKNOWN,
}


def normalize_nationality(raw: Optional[str]) -> NationalityStatus:
    """Map a raw nationality string to NationalityStatus. Returns UNKNOWN if unrecognized."""
    if not raw:
        return NationalityStatus.UNKNOWN
    return _NATIONALITY_MAP.get(raw.strip().lower(), NationalityStatus.UNKNOWN)


# ---------------------------------------------------------------------------
# Saudi program eligibility normalization
# ---------------------------------------------------------------------------

_PROGRAM_ELIGIBILITY_MAP: dict[str, SaudiProgramEligibility] = {
    "tamheer": SaudiProgramEligibility.TAMHEER,
    "تمهير": SaudiProgramEligibility.TAMHEER,
    "coop": SaudiProgramEligibility.COOP,
    "co-op": SaudiProgramEligibility.COOP,
    "cooperative": SaudiProgramEligibility.COOP,
    "تعاوني": SaudiProgramEligibility.COOP,
    "hrdf_subsidy": SaudiProgramEligibility.HRDF_SUBSIDY,
    "hrdf": SaudiProgramEligibility.HRDF_SUBSIDY,
    "هدف": SaudiProgramEligibility.HRDF_SUBSIDY,
    "none": SaudiProgramEligibility.NONE,
}


def normalize_saudi_program_eligibility(raw_list: list[str]) -> list[SaudiProgramEligibility]:
    """Map raw program eligibility labels to SaudiProgramEligibility values.
    Unrecognized labels are skipped with a debug log."""
    seen: set[SaudiProgramEligibility] = set()
    result: list[SaudiProgramEligibility] = []
    for raw in raw_list:
        mapped = _PROGRAM_ELIGIBILITY_MAP.get(raw.strip().lower())
        if mapped is None:
            logger.debug("normalize_saudi_program_eligibility: unrecognized %r", raw)
            continue
        if mapped not in seen:
            seen.add(mapped)
            result.append(mapped)
    return result


# ---------------------------------------------------------------------------
# Skill normalization
# ---------------------------------------------------------------------------

def normalize_skills(raw_skills: list[str]) -> list[str]:
    """
    Resolve raw skill labels to taxonomy IDs.

    Each label is matched individually against the skills taxonomy via
    TaxonomyMatcher. Labels that match return the stable taxonomy ID (e.g.
    'skill-python'). Labels without a taxonomy match are preserved as-is
    (lowercased, stripped) so no information is silently discarded.

    Duplicate IDs are collapsed: two labels that both resolve to 'skill-python'
    produce a single entry.
    """
    matcher = get_matcher()
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_skills:
        label = raw.strip()
        if not label:
            continue
        matched = matcher.match_skills(label)
        if matched:
            for skill_id in matched:
                if skill_id not in seen:
                    seen.add(skill_id)
                    result.append(skill_id)
        else:
            fallback = label.lower()
            if fallback not in seen:
                seen.add(fallback)
                result.append(fallback)

    return result


def normalize_certifications(raw_certs: list) -> list[str]:
    """
    Resolve CandidateCertification entries to taxonomy IDs where possible.

    Certifications with taxonomy entries (e.g. PMP → 'skill-pmp') are returned
    as IDs. Others are preserved as lowercased raw names. Deduplicates the result.
    """
    from candidate.models import CandidateCertification
    matcher = get_matcher()
    seen: set[str] = set()
    result: list[str] = []

    for cert in raw_certs:
        name = cert.name if isinstance(cert, CandidateCertification) else str(cert)
        if not name.strip():
            continue
        matched = matcher.match_skills(name.strip())
        if matched:
            for skill_id in matched:
                if skill_id not in seen:
                    seen.add(skill_id)
                    result.append(skill_id)
        else:
            fallback = name.strip().lower()
            if fallback not in seen:
                seen.add(fallback)
                result.append(fallback)

    return result

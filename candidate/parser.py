"""
Candidate input parser for Saudi Career Ops.

Converts a raw dict (from a manual form, API payload, or future CV parser output)
into a structured RawCandidateInput. Responsibilities:

  - Extract fields from expected key names, in English and Arabic variants
  - Coerce basic types (strings, lists, ints, booleans)
  - Build structured sub-records (CandidateExperience, CandidateEducation, etc.)
  - Handle missing or malformed fields without raising

This layer does NOT normalize. Skill labels stay as typed, locations stay as
entered, language labels are not yet mapped to enums. All of that happens in
normalizer.py, which runs after parsing.

Arabic field key support covers the most common bilingual form patterns. Keys
not in the alias table pass through after lowercasing and underscore normalization.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from candidate.models import (
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateProfileMetadata,
    RawCandidateInput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Arabic → canonical English field name mappings
# ---------------------------------------------------------------------------

_FIELD_ALIASES: dict[str, str] = {
    # Identity
    "الاسم": "name",
    "الاسم بالعربي": "name_arabic",
    "الاسم الكامل": "name",
    "الاسم بالإنجليزي": "name",
    # Skills
    "المهارات": "skills",
    "الخبرات التقنية": "skills",
    "المهارات التقنية": "skills",
    # Languages
    "اللغات": "languages",
    "اللغة": "languages",
    # Location
    "الموقع المفضل": "preferred_locations",
    "الموقع": "preferred_locations",
    "مستعد للانتقال": "willing_to_relocate",
    # Employment
    "نوع العمل المفضل": "employment_preferences",
    "نوع التوظيف": "employment_preferences",
    # Nationality
    "الجنسية": "nationality_status",
    # Experience
    "الخبرة": "experiences",
    "الخبرات": "experiences",
    "خبرة العمل": "experiences",
    # Education
    "التعليم": "education",
    "المؤهل العلمي": "education",
    # Certifications
    "الشهادات": "certifications",
    "الشهادات المهنية": "certifications",
    # Overrides
    "سنوات الخبرة": "years_experience",
    "المسمى الوظيفي الحالي": "seniority",
}


# ---------------------------------------------------------------------------
# Training-role title markers (used to auto-set is_training on experience entries)
# ---------------------------------------------------------------------------

_TRAINING_MARKERS = frozenset([
    "tamheer", "تمهير", "trainee", "متدرب", "coop", "co-op",
    "cooperative", "تعاون", "intern", "تدريب",
])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _canonical_key(key: str) -> str:
    mapped = _FIELD_ALIASES.get(key.strip())
    if mapped:
        return mapped
    return key.strip().lower().replace(" ", "_")


def _to_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [value]


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.lower().strip()
        if low in ("true", "yes", "1", "نعم"):
            return True
        if low in ("false", "no", "0", "لا"):
            return False
    return None


def _is_training_title(title: str) -> bool:
    title_lower = title.lower()
    return any(marker in title_lower for marker in _TRAINING_MARKERS)


def _remap_keys(raw: dict) -> dict:
    return {_canonical_key(k): v for k, v in raw.items()}


def _compute_hash(raw: dict) -> str:
    serialized = json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Sub-record parsers
# ---------------------------------------------------------------------------

def _parse_experience(entry: Any) -> Optional[CandidateExperience]:
    if not isinstance(entry, dict):
        return None
    d = _remap_keys(entry)
    title = str(d.get("title") or "").strip()
    if not title:
        return None
    explicit_training = bool(_to_bool(d.get("is_training")) or False)
    return CandidateExperience(
        title=title,
        company=str(d.get("company") or "").strip() or None,
        start_year=_to_int(d.get("start_year")),
        end_year=_to_int(d.get("end_year")),
        is_current=bool(_to_bool(d.get("is_current")) or False),
        is_training=explicit_training or _is_training_title(title),
        description=str(d.get("description") or "").strip() or None,
    )


def _parse_education(entry: Any) -> Optional[CandidateEducation]:
    if not isinstance(entry, dict):
        return None
    d = _remap_keys(entry)
    return CandidateEducation(
        institution=str(d.get("institution") or "").strip() or None,
        degree=str(d.get("degree") or "").strip() or None,
        field_of_study=str(d.get("field_of_study") or "").strip() or None,
        graduation_year=_to_int(d.get("graduation_year")),
        is_current=bool(_to_bool(d.get("is_current")) or False),
    )


def _parse_certification(entry: Any) -> Optional[CandidateCertification]:
    if isinstance(entry, str):
        name = entry.strip()
        return CandidateCertification(name=name) if name else None
    if not isinstance(entry, dict):
        return None
    d = _remap_keys(entry)
    name = str(d.get("name") or "").strip()
    if not name:
        return None
    return CandidateCertification(
        name=name,
        issuer=str(d.get("issuer") or "").strip() or None,
        year=_to_int(d.get("year")),
    )


def _parse_language(entry: Any) -> Optional[CandidateLanguage]:
    if isinstance(entry, str):
        label = entry.strip()
        return CandidateLanguage(language=label) if label else None
    if not isinstance(entry, dict):
        return None
    d = _remap_keys(entry)
    lang = str(d.get("language") or "").strip()
    if not lang:
        return None
    return CandidateLanguage(
        language=lang,
        proficiency=str(d.get("proficiency") or "").strip() or None,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_candidate(
    raw: dict,
    source: str = "manual_form",
) -> RawCandidateInput:
    """
    Parse a raw input dict into a RawCandidateInput.

    Handles both English and Arabic field keys. Missing fields are silently
    skipped and left as None or empty lists. Type coercion is permissive:
    a comma-separated string for skills is split into a list; a bare string
    boolean is interpreted by keyword.

    The original dict is preserved unmodified in RawCandidateInput.raw.

    Args:
        raw:    Source dict from a form, API, or test fixture.
        source: Ingestion source label stored in metadata.
    """
    d = _remap_keys(raw)

    candidate_id = str(d.get("id") or d.get("candidate_id") or "").strip()
    if not candidate_id:
        logger.warning("parse_candidate: input has no 'id' field")

    name = str(d.get("name") or "").strip() or None
    name_arabic = str(d.get("name_arabic") or "").strip() or None

    raw_skills = [
        str(s).strip()
        for s in _to_list(d.get("skills") or d.get("raw_skills"))
        if str(s).strip()
    ]

    certifications = [
        c for c in (_parse_certification(e) for e in _to_list(d.get("certifications")))
        if c is not None
    ]

    raw_languages = [
        lang for lang in (_parse_language(e) for e in _to_list(d.get("languages")))
        if lang is not None
    ]

    preferred_locations = [
        str(loc).strip()
        for loc in _to_list(d.get("preferred_locations"))
        if str(loc).strip()
    ]

    willing_to_relocate = _to_bool(d.get("willing_to_relocate"))

    raw_employment_preferences = [
        str(p).strip()
        for p in _to_list(d.get("employment_preferences"))
        if str(p).strip()
    ]

    nationality_status = str(d.get("nationality_status") or "").strip() or None

    raw_saudi_program_eligibility = [
        str(p).strip()
        for p in _to_list(d.get("saudi_program_eligibility"))
        if str(p).strip()
    ]

    experiences = [
        exp for exp in (_parse_experience(e) for e in _to_list(d.get("experiences")))
        if exp is not None
    ]

    education = [
        edu for edu in (_parse_education(e) for e in _to_list(d.get("education")))
        if edu is not None
    ]

    years_experience_override = _to_float(d.get("years_experience"))
    seniority_override = str(d.get("seniority") or "").strip() or None

    metadata = CandidateProfileMetadata(
        source=source,
        created_at=datetime.now(tz=timezone.utc),
        raw_input_hash=_compute_hash(raw),
    )

    return RawCandidateInput(
        id=candidate_id,
        name=name,
        name_arabic=name_arabic,
        raw_skills=raw_skills,
        certifications=certifications,
        raw_languages=raw_languages,
        preferred_locations=preferred_locations,
        willing_to_relocate=willing_to_relocate,
        raw_employment_preferences=raw_employment_preferences,
        nationality_status=nationality_status,
        raw_saudi_program_eligibility=raw_saudi_program_eligibility,
        experiences=experiences,
        education=education,
        years_experience_override=years_experience_override,
        seniority_override=seniority_override,
        metadata=metadata,
        raw=raw,
    )

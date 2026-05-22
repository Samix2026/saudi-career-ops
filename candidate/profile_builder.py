"""
Profile builder — assembles a CandidateProfile from a RawCandidateInput.

This is the final step in the candidate ingestion pipeline:

  1. Calls normalizer functions to resolve raw fields into typed values
  2. Infers years_experience from the experience timeline if not stated explicitly
  3. Infers seniority from job titles, falling back to year-band approximation
  4. Generates Saudi program eligibility hints from training entries and enrollment
  5. Computes profile completeness

Inferred values are conservative estimates grounded in the available data.
When inference cannot be supported by the input, the field is left as None.
The one exception is profile_completeness, which is always computed (a score
of 0.0 is a valid result that signals a very sparse profile, not an error).

None of the inference here is authoritative:
  - Years of experience from dates is an approximation; overlapping roles
    over-count and undated roles are excluded entirely.
  - Seniority from year bands is a coarse fallback; title-based derivation
    is used first wherever possible.
  - Program eligibility hints require human verification — they signal that
    the data suggests eligibility, not that eligibility is confirmed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from ingestion.models.job_posting import Seniority
from ingestion.parsers.job_parser import extract_seniority, get_matcher
from matching.models import (
    CandidateProfile,
    NationalityStatus,
    SaudiProgramEligibility,
)
from candidate.models import CandidateEducation, CandidateExperience, RawCandidateInput
from candidate.normalizer import (
    normalize_certifications,
    normalize_employment_preferences,
    normalize_languages,
    normalize_locations,
    normalize_nationality,
    normalize_saudi_program_eligibility,
    normalize_skills,
)

logger = logging.getLogger(__name__)

_CURRENT_YEAR = datetime.now(tz=timezone.utc).year

# ---------------------------------------------------------------------------
# Seniority inference bands (years of professional experience → Seniority level)
# Used only as a last resort when no title-based seniority can be derived.
# Thresholds are coarse industry approximations, not precise classifications.
# ---------------------------------------------------------------------------

_SENIORITY_BANDS: list[tuple[float, Seniority]] = [
    (0.0,  Seniority.ENTRY),
    (1.5,  Seniority.JUNIOR),
    (3.0,  Seniority.MID),
    (5.5,  Seniority.SENIOR),
    (9.0,  Seniority.LEAD),
    (13.0, Seniority.MANAGER),
]


# ---------------------------------------------------------------------------
# Experience utilities
# ---------------------------------------------------------------------------

def _duration_years(exp: CandidateExperience) -> Optional[float]:
    """Years of duration for one experience entry. None if start_year is missing."""
    if exp.start_year is None:
        return None
    end = exp.end_year if (exp.end_year and not exp.is_current) else _CURRENT_YEAR
    return max(0.0, float(end - exp.start_year))


def infer_years_experience(experiences: list[CandidateExperience]) -> Optional[float]:
    """
    Sum professional experience years from dated experience entries.

    Training entries (Tamheer, co-op, internships) are excluded. If no
    non-training entries have start years, returns None rather than 0.

    Approximation note: overlapping concurrent roles are not detected and
    will over-count. Undated roles are excluded, which may under-count.
    """
    total = 0.0
    has_any = False
    for exp in experiences:
        if exp.is_training:
            continue
        duration = _duration_years(exp)
        if duration is None:
            continue
        has_any = True
        total += duration
    return round(total, 1) if has_any else None


# ---------------------------------------------------------------------------
# Seniority inference
# ---------------------------------------------------------------------------

def infer_seniority(
    seniority_override: Optional[str],
    experiences: list[CandidateExperience],
    years_experience: Optional[float],
) -> Optional[Seniority]:
    """
    Determine seniority via three strategies, in priority order:

    1. Explicit seniority_override from the raw input (most trusted).
    2. Title-based match on the most recent non-training experience entry,
       using the same taxonomy + regex pipeline as the job parser.
    3. Year-band approximation from years_experience (least trusted, logged).

    Returns None if no strategy produces a result rather than defaulting
    to a plausible-sounding level.
    """
    # Strategy 1: explicit override
    if seniority_override:
        try:
            return Seniority(seniority_override.strip().lower())
        except ValueError:
            pass
        derived = extract_seniority(seniority_override)
        if derived:
            return derived
        logger.debug("infer_seniority: unrecognized seniority_override %r", seniority_override)

    # Strategy 2: title-based match on most recent non-training role
    professional = [e for e in experiences if not e.is_training]
    professional.sort(key=lambda e: e.start_year or 0, reverse=True)
    for exp in professional:
        seniority = extract_seniority(exp.title)
        if seniority:
            return seniority

    # Strategy 3: year-band approximation
    if years_experience is not None:
        for threshold, level in reversed(_SENIORITY_BANDS):
            if years_experience >= threshold:
                logger.debug(
                    "infer_seniority: %.1f years → %s (year-band fallback; no title match)",
                    years_experience,
                    level.value,
                )
                return level

    return None


# ---------------------------------------------------------------------------
# Saudi program eligibility hints
# ---------------------------------------------------------------------------

def hint_saudi_program_eligibility(
    nationality: NationalityStatus,
    explicit_eligibility: list[SaudiProgramEligibility],
    experiences: list[CandidateExperience],
    education: list[CandidateEducation],
) -> list[SaudiProgramEligibility]:
    """
    Produce a best-effort eligibility list from the available signals.

    Priority order:
    1. Explicit eligibility from raw input — always included.
    2. Training experience entry with 'tamheer' or 'تمهير' in the title
       → hints TAMHEER (candidate has participated in the program).
    3. Current education enrollment → hints COOP (enrolled student).
    4. Expatriate with no other eligibility → appends NONE.

    These are hints. They require human confirmation before being treated as
    authoritative. Eligibility depends on HRDF registration, enrollment status,
    and other criteria this system cannot verify from profile data alone.
    """
    result: list[SaudiProgramEligibility] = list(explicit_eligibility)
    seen: set[SaudiProgramEligibility] = set(result)

    for exp in experiences:
        if exp.is_training and (
            "tamheer" in exp.title.lower() or "تمهير" in exp.title
        ):
            if SaudiProgramEligibility.TAMHEER not in seen:
                result.append(SaudiProgramEligibility.TAMHEER)
                seen.add(SaudiProgramEligibility.TAMHEER)
                logger.debug("hint_saudi_program_eligibility: TAMHEER hinted from %r", exp.title)

    for edu in education:
        if edu.is_current and SaudiProgramEligibility.COOP not in seen:
            result.append(SaudiProgramEligibility.COOP)
            seen.add(SaudiProgramEligibility.COOP)
            logger.debug("hint_saudi_program_eligibility: COOP hinted from current enrollment")

    if nationality == NationalityStatus.EXPATRIATE and not result:
        result.append(SaudiProgramEligibility.NONE)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_profile(raw: RawCandidateInput) -> CandidateProfile:
    """
    Build a CandidateProfile from a RawCandidateInput.

    Runs all normalization functions, applies experience and seniority inference,
    generates Saudi program eligibility hints, and computes profile_completeness.
    The resulting CandidateProfile is ready to be passed to the matching engine.
    """
    skills = normalize_skills(raw.raw_skills)
    certifications = normalize_certifications(raw.certifications)
    languages = normalize_languages(raw.raw_languages)
    locations = normalize_locations(raw.preferred_locations)
    employment_prefs = normalize_employment_preferences(raw.raw_employment_preferences)
    nationality = normalize_nationality(raw.nationality_status)
    explicit_program_eligibility = normalize_saudi_program_eligibility(
        raw.raw_saudi_program_eligibility
    )

    years_exp: Optional[float] = raw.years_experience_override
    if years_exp is None and raw.experiences:
        years_exp = infer_years_experience(raw.experiences)

    seniority = infer_seniority(
        seniority_override=raw.seniority_override,
        experiences=raw.experiences,
        years_experience=years_exp,
    )

    program_eligibility = hint_saudi_program_eligibility(
        nationality=nationality,
        explicit_eligibility=explicit_program_eligibility,
        experiences=raw.experiences,
        education=raw.education,
    )

    profile = CandidateProfile(
        id=raw.id,
        name=raw.name or raw.name_arabic,
        years_experience=years_exp,
        seniority=seniority,
        skills=skills,
        certifications=certifications,
        languages=languages,
        preferred_locations=locations,
        willing_to_relocate=raw.willing_to_relocate if raw.willing_to_relocate is not None else False,
        employment_preferences=employment_prefs,
        nationality_status=nationality,
        saudi_program_eligibility=program_eligibility,
    )

    profile.compute_completeness()
    return profile

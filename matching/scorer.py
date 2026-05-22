"""
Deterministic weighted scorer for candidate-job matching.

Every factor returns a ComponentScore with an explicit score (0-1), a weight,
and a plain-English detail string. No machine learning, no embeddings. The
total_score on MatchResult is the sum of weighted component scores scaled to
0-100. Nothing is adjusted after that computation.

Weights are configurable via ScoringWeights. The six factors and their defaults:

  skill_overlap        0.35  — fraction of job-required skills the candidate holds
  seniority_alignment  0.20  — band distance between candidate and role seniority
  employment_type      0.15  — candidate preference vs. job type
  language             0.15  — working language compatibility
  location             0.10  — geographic alignment, factoring in relocation willingness
  saudi_program        0.05  — Tamheer eligibility and Saudization signal alignment
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ingestion.models.job_posting import EmploymentType, JobPosting, Language, Seniority
from matching.explanations import build_explanation
from matching.models import (
    CandidateProfile,
    ComponentScore,
    ConfidenceLevel,
    MatchResult,
    NationalityStatus,
    SaudiProgramEligibility,
)


_SENIORITY_RANK: dict[Seniority, int] = {
    Seniority.ENTRY: 0,
    Seniority.JUNIOR: 1,
    Seniority.MID: 2,
    Seniority.SENIOR: 3,
    Seniority.LEAD: 4,
    Seniority.MANAGER: 5,
    Seniority.DIRECTOR: 6,
    Seniority.EXECUTIVE: 7,
}

_LOCATION_TOKENS = {
    "riyadh", "jeddah", "dammam", "mecca", "medina", "khobar", "abha",
    "tabuk", "qassim", "jubail", "yanbu", "ksa", "saudi", "arabia",
    "remote", "anywhere",
}


@dataclass
class ScoringWeights:
    """
    Relative weights for each scoring factor. Must sum to 1.0.
    Adjust per deployment context; defaults reflect a general Saudi market match.
    """
    skill_overlap: float = 0.35
    seniority_alignment: float = 0.20
    employment_type: float = 0.15
    language: float = 0.15
    location: float = 0.10
    saudi_program: float = 0.05

    def validate(self) -> None:
        total = (
            self.skill_overlap
            + self.seniority_alignment
            + self.employment_type
            + self.language
            + self.location
            + self.saudi_program
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"ScoringWeights must sum to 1.0, got {total:.6f}")


DEFAULT_WEIGHTS = ScoringWeights()


def _normalize_skill(s: str) -> str:
    """Normalize a skill string for comparison: lowercase, strip 'skill-' prefix, spaces for dashes."""
    s = s.lower().strip()
    if s.startswith("skill-"):
        s = s[6:]
    return s.replace("-", " ").replace("_", " ")


def _location_tokens(location: str) -> set[str]:
    return {t.lower().strip(",.()") for t in location.split() if t.lower().strip(",.()") in _LOCATION_TOKENS}


def score_skill_overlap(
    candidate: CandidateProfile,
    job: JobPosting,
    weight: float,
) -> ComponentScore:
    candidate_skills = {_normalize_skill(s) for s in candidate.all_skills}
    job_skills = {_normalize_skill(s) for s in job.skills}

    if not job_skills:
        return ComponentScore(
            factor="skill_overlap",
            score=0.5,
            weight=weight,
            weighted_score=0.5 * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Job posting lists no skills; overlap cannot be computed.",
        )

    if not candidate_skills:
        return ComponentScore(
            factor="skill_overlap",
            score=0.0,
            weight=weight,
            weighted_score=0.0,
            confidence=ConfidenceLevel.LOW,
            detail="Candidate profile lists no skills; overlap cannot be computed.",
        )

    matched = candidate_skills & job_skills
    score = len(matched) / len(job_skills)
    confidence = ConfidenceLevel.HIGH if len(job_skills) >= 3 else ConfidenceLevel.MEDIUM

    if matched:
        matched_display = sorted(matched)
        preview = ", ".join(matched_display[:5])
        suffix = "..." if len(matched_display) > 5 else ""
        detail = (
            f"Candidate matches {len(matched)}/{len(job_skills)} required skills: "
            f"{preview}{suffix}."
        )
    else:
        detail = f"No overlap between candidate skills and {len(job_skills)} listed job requirements."

    return ComponentScore(
        factor="skill_overlap",
        score=score,
        weight=weight,
        weighted_score=score * weight,
        confidence=confidence,
        detail=detail,
    )


def score_seniority_alignment(
    candidate: CandidateProfile,
    job: JobPosting,
    weight: float,
) -> ComponentScore:
    c_seniority = candidate.seniority
    j_seniority = job.seniority

    if c_seniority is None or c_seniority == Seniority.UNKNOWN:
        return ComponentScore(
            factor="seniority_alignment",
            score=0.5,
            weight=weight,
            weighted_score=0.5 * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Candidate seniority not stated; alignment cannot be assessed.",
        )

    if j_seniority is None or j_seniority == Seniority.UNKNOWN:
        return ComponentScore(
            factor="seniority_alignment",
            score=0.5,
            weight=weight,
            weighted_score=0.5 * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Job seniority level not stated; alignment cannot be assessed.",
        )

    c_rank = _SENIORITY_RANK[c_seniority]
    j_rank = _SENIORITY_RANK[j_seniority]
    delta = abs(c_rank - j_rank)

    # 0 bands = 1.0, 1 = 0.6, 2 = 0.2, 3+ = 0.0
    score = max(0.0, 1.0 - delta * 0.4)

    if delta == 0:
        detail = f"Seniority is an exact match: both {c_seniority.value}."
    else:
        direction = "above" if c_rank > j_rank else "below"
        qualifier = "one band" if delta == 1 else f"{delta} bands"
        detail = (
            f"Candidate seniority ({c_seniority.value}) is {qualifier} {direction} "
            f"the posting ({j_seniority.value})."
        )
        if delta >= 3:
            detail += " Significant mismatch."

    return ComponentScore(
        factor="seniority_alignment",
        score=score,
        weight=weight,
        weighted_score=score * weight,
        confidence=ConfidenceLevel.HIGH,
        detail=detail,
    )


def score_employment_type(
    candidate: CandidateProfile,
    job: JobPosting,
    weight: float,
) -> ComponentScore:
    job_type = job.employment_type

    if job_type is None or job_type == EmploymentType.UNKNOWN:
        return ComponentScore(
            factor="employment_type",
            score=0.7,
            weight=weight,
            weighted_score=0.7 * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Job employment type not stated; assuming general compatibility.",
        )

    if not candidate.employment_preferences:
        return ComponentScore(
            factor="employment_type",
            score=0.7,
            weight=weight,
            weighted_score=0.7 * weight,
            confidence=ConfidenceLevel.LOW,
            detail=(
                f"Candidate has no stated employment type preferences; "
                f"job is {job_type.value}."
            ),
        )

    if job_type in candidate.employment_preferences:
        return ComponentScore(
            factor="employment_type",
            score=1.0,
            weight=weight,
            weighted_score=weight,
            confidence=ConfidenceLevel.HIGH,
            detail=f"Job type ({job_type.value}) matches candidate preference.",
        )

    return ComponentScore(
        factor="employment_type",
        score=0.1,
        weight=weight,
        weighted_score=0.1 * weight,
        confidence=ConfidenceLevel.HIGH,
        detail=(
            f"Job type ({job_type.value}) is not among candidate's preferred types: "
            f"{', '.join(p.value for p in candidate.employment_preferences)}."
        ),
    )


def score_language(
    candidate: CandidateProfile,
    job: JobPosting,
    weight: float,
) -> ComponentScore:
    job_lang = job.language

    if job_lang in (Language.UNKNOWN, Language.MIXED):
        return ComponentScore(
            factor="language",
            score=0.7,
            weight=weight,
            weighted_score=0.7 * weight,
            confidence=ConfidenceLevel.LOW,
            detail=f"Job language is {job_lang.value}; language compatibility cannot be precisely assessed.",
        )

    if not candidate.languages:
        return ComponentScore(
            factor="language",
            score=0.5,
            weight=weight,
            weighted_score=0.5 * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Candidate language profile not stated; compatibility unknown.",
        )

    if job_lang in candidate.languages:
        return ComponentScore(
            factor="language",
            score=1.0,
            weight=weight,
            weighted_score=weight,
            confidence=ConfidenceLevel.HIGH,
            detail=f"Candidate is proficient in {job_lang.value}, matching the job's working language.",
        )

    candidate_langs = ", ".join(lang.value for lang in candidate.languages)
    return ComponentScore(
        factor="language",
        score=0.2,
        weight=weight,
        weighted_score=0.2 * weight,
        confidence=ConfidenceLevel.HIGH,
        detail=(
            f"Job requires {job_lang.value} but candidate's languages are: {candidate_langs}."
        ),
    )


def score_location(
    candidate: CandidateProfile,
    job: JobPosting,
    weight: float,
) -> ComponentScore:
    job_tokens = _location_tokens(job.location)
    is_remote_job = "remote" in job_tokens

    if is_remote_job:
        score = 0.9 if candidate.preferred_locations else 0.8
        return ComponentScore(
            factor="location",
            score=score,
            weight=weight,
            weighted_score=score * weight,
            confidence=ConfidenceLevel.HIGH if candidate.preferred_locations else ConfidenceLevel.MEDIUM,
            detail="Job is remote; geography is not a constraint for this role.",
        )

    if not candidate.preferred_locations:
        score = 0.6 if candidate.willing_to_relocate else 0.5
        return ComponentScore(
            factor="location",
            score=score,
            weight=weight,
            weighted_score=score * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Candidate has no stated location preferences; match is indeterminate.",
        )

    for pref in candidate.preferred_locations:
        pref_tokens = _location_tokens(pref)
        if "remote" in pref_tokens and is_remote_job:
            return ComponentScore(
                factor="location",
                score=0.9,
                weight=weight,
                weighted_score=0.9 * weight,
                confidence=ConfidenceLevel.HIGH,
                detail="Candidate prefers remote work and the role is remote.",
            )
        if pref_tokens & job_tokens:
            return ComponentScore(
                factor="location",
                score=1.0,
                weight=weight,
                weighted_score=weight,
                confidence=ConfidenceLevel.HIGH,
                detail=f"Job location ({job.location}) aligns with candidate preference ({pref}).",
            )

    if candidate.willing_to_relocate:
        return ComponentScore(
            factor="location",
            score=0.6,
            weight=weight,
            weighted_score=0.6 * weight,
            confidence=ConfidenceLevel.MEDIUM,
            detail=(
                f"Job location ({job.location}) does not match candidate preferences, "
                f"but candidate is willing to relocate."
            ),
        )

    return ComponentScore(
        factor="location",
        score=0.1,
        weight=weight,
        weighted_score=0.1 * weight,
        confidence=ConfidenceLevel.HIGH,
        detail=(
            f"Job location ({job.location}) does not match any candidate preference "
            f"and candidate is not willing to relocate."
        ),
    )


def score_saudi_program(
    candidate: CandidateProfile,
    job: JobPosting,
    weight: float,
) -> ComponentScore:
    is_tamheer = job.employment_type == EmploymentType.TAMHEER
    has_saudization = bool(job.saudization_signal)

    if is_tamheer:
        if candidate.nationality_status == NationalityStatus.EXPATRIATE:
            return ComponentScore(
                factor="saudi_program",
                score=0.0,
                weight=weight,
                weighted_score=0.0,
                confidence=ConfidenceLevel.HIGH,
                detail="Tamheer program is restricted to Saudi nationals; candidate is expatriate.",
            )
        if SaudiProgramEligibility.TAMHEER in candidate.saudi_program_eligibility:
            return ComponentScore(
                factor="saudi_program",
                score=1.0,
                weight=weight,
                weighted_score=weight,
                confidence=ConfidenceLevel.HIGH,
                detail="Candidate is registered for the Tamheer program; matches this role type.",
            )
        if candidate.nationality_status == NationalityStatus.SAUDI_NATIONAL:
            return ComponentScore(
                factor="saudi_program",
                score=0.7,
                weight=weight,
                weighted_score=0.7 * weight,
                confidence=ConfidenceLevel.MEDIUM,
                detail=(
                    "Tamheer role; candidate is a Saudi national but Tamheer enrollment "
                    "status is not confirmed."
                ),
            )
        return ComponentScore(
            factor="saudi_program",
            score=0.4,
            weight=weight,
            weighted_score=0.4 * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Tamheer role; candidate nationality and eligibility status are unknown.",
        )

    if has_saudization:
        if candidate.nationality_status == NationalityStatus.SAUDI_NATIONAL:
            return ComponentScore(
                factor="saudi_program",
                score=1.0,
                weight=weight,
                weighted_score=weight,
                confidence=ConfidenceLevel.HIGH,
                detail="Job has Saudization preference; candidate is a Saudi national.",
            )
        if candidate.nationality_status == NationalityStatus.GCC_NATIONAL:
            return ComponentScore(
                factor="saudi_program",
                score=0.7,
                weight=weight,
                weighted_score=0.7 * weight,
                confidence=ConfidenceLevel.MEDIUM,
                detail=(
                    "Job signals Saudization preference; candidate is a GCC national "
                    "(partial Nitaqat credit in some employer schemes)."
                ),
            )
        if candidate.nationality_status == NationalityStatus.EXPATRIATE:
            return ComponentScore(
                factor="saudi_program",
                score=0.2,
                weight=weight,
                weighted_score=0.2 * weight,
                confidence=ConfidenceLevel.HIGH,
                detail=(
                    "Job signals Saudization preference; candidate is expatriate — "
                    "hiring is possible but preference is clearly stated."
                ),
            )
        return ComponentScore(
            factor="saudi_program",
            score=0.5,
            weight=weight,
            weighted_score=0.5 * weight,
            confidence=ConfidenceLevel.LOW,
            detail="Job signals Saudization preference; candidate nationality is unknown.",
        )

    return ComponentScore(
        factor="saudi_program",
        score=0.8,
        weight=weight,
        weighted_score=0.8 * weight,
        confidence=ConfidenceLevel.HIGH,
        detail="No Saudization constraint or government program requirement detected in this posting.",
    )


def _derive_overall_confidence(components: list[ComponentScore]) -> ConfidenceLevel:
    confidence_values = {c.confidence for c in components}
    if ConfidenceLevel.LOW in confidence_values:
        return ConfidenceLevel.LOW
    if ConfidenceLevel.MEDIUM in confidence_values:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.HIGH


class Scorer:
    """
    Deterministic, rule-based candidate-job matcher.

    Produces a MatchResult with a 0-100 total_score and a fully populated
    MatchExplanation. Scoring weights are configurable; all other logic is fixed.
    """

    def __init__(self, weights: Optional[ScoringWeights] = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS
        self.weights.validate()

    def score(self, candidate: CandidateProfile, job: JobPosting) -> MatchResult:
        w = self.weights

        components = [
            score_skill_overlap(candidate, job, w.skill_overlap),
            score_seniority_alignment(candidate, job, w.seniority_alignment),
            score_employment_type(candidate, job, w.employment_type),
            score_language(candidate, job, w.language),
            score_location(candidate, job, w.location),
            score_saudi_program(candidate, job, w.saudi_program),
        ]

        components.sort(key=lambda c: c.weighted_score, reverse=True)

        total_score = sum(c.weighted_score for c in components) * 100.0
        confidence = _derive_overall_confidence(components)
        explanation = build_explanation(candidate, job, components)

        return MatchResult(
            candidate_id=candidate.id,
            job_id=job.id,
            total_score=total_score,
            confidence=confidence,
            explanation=explanation,
            has_red_flags=bool(explanation.red_flags),
            is_tamheer_role=(job.employment_type == EmploymentType.TAMHEER),
        )

"""
Data models for the Saudi Career Ops matching layer.

Three types are defined here:

  CandidateProfile  — structured representation of a candidate's attributes
  MatchResult       — scored output of one candidate-job comparison
  MatchExplanation  — human-readable breakdown of why a score was produced

These types are consumed by scorer.py and explanations.py. They do not depend
on the ingestion layer models, making the matching layer independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ingestion.models.job_posting import EmploymentType, Language, Seniority


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SaudiProgramEligibility(str, Enum):
    """
    Which Saudi government employment programs the candidate is eligible for.
    A candidate may be eligible for multiple programs simultaneously.
    """
    TAMHEER = "tamheer"      # HRDF on-the-job training; Saudi nationals only
    COOP = "coop"            # University cooperative training; enrolled students only
    HRDF_SUBSIDY = "hrdf_subsidy"  # General HRDF wage subsidy; Saudi nationals in private sector
    NONE = "none"            # No government program eligibility (e.g. expatriate candidates)


class NationalityStatus(str, Enum):
    SAUDI_NATIONAL = "saudi_national"
    GCC_NATIONAL = "gcc_national"
    EXPATRIATE = "expatriate"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence in a match component, based on data completeness."""
    HIGH = "high"      # Both sides of the comparison have full data
    MEDIUM = "medium"  # One side has partial data
    LOW = "low"        # One or both sides are missing key information
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# CandidateProfile
# ---------------------------------------------------------------------------

@dataclass
class CandidateProfile:
    """
    Structured representation of a candidate's professional attributes.

    All fields are optional beyond id and name. A matching run with sparse
    data produces lower-confidence scores, not errors. Fields should only be
    populated with confirmed information — do not estimate or interpolate.
    """

    id: str
    """Stable identifier for this profile. Opaque to the matching engine."""

    name: Optional[str] = None
    """Display name. Not used in scoring. Present for human-readable output only."""

    # --- Experience ---
    years_experience: Optional[float] = None
    """
    Total professional years of experience. Tamheer and co-op placements should
    be weighed carefully when computing this — they are training, not equivalent
    to full professional experience in most contexts.
    """

    seniority: Optional[Seniority] = None
    """Self-reported or CV-derived seniority level."""

    # --- Skills ---
    skills: list[str] = field(default_factory=list)
    """
    Normalized skill IDs from data/taxonomies/skills.json (e.g. 'skill-sql').
    Raw text skill labels are not accepted here — normalize via TaxonomyMatcher
    before constructing a CandidateProfile.
    """

    certifications: list[str] = field(default_factory=list)
    """
    Certification skill IDs (e.g. 'skill-pmp'). These are modeled as skills
    using the taxonomy's 'certification' category — no separate taxonomy needed.
    """

    # --- Language ---
    languages: list[Language] = field(default_factory=list)
    """
    Languages the candidate can work in professionally. Order is not significant.
    Use Language enum values (Language.ARABIC, Language.ENGLISH).
    """

    # --- Location ---
    preferred_locations: list[str] = field(default_factory=list)
    """
    Preferred work locations as free strings (e.g. 'Riyadh', 'Remote', 'KSA').
    Location matching is fuzzy — the scorer normalizes and compares these.
    """

    willing_to_relocate: bool = False
    """Whether the candidate is open to relocating for the right role."""

    # --- Employment preferences ---
    employment_preferences: list[EmploymentType] = field(default_factory=list)
    """
    Employment types the candidate is interested in or willing to accept.
    An empty list means no stated preference — not that all types are rejected.
    """

    # --- Saudi context ---
    nationality_status: NationalityStatus = NationalityStatus.UNKNOWN
    """
    Nationality classification relevant to Saudization and program eligibility.
    This affects which roles and programs the candidate is realistically
    eligible for — it is not used for any purpose beyond match analysis.
    """

    saudi_program_eligibility: list[SaudiProgramEligibility] = field(default_factory=list)
    """
    Government programs this candidate is eligible for. This must be set
    explicitly — the engine does not infer eligibility from nationality alone,
    because program eligibility depends on HRDF registration status, enrollment
    status, and other criteria not captured in the profile.
    """

    # --- Computed / metadata ---
    profile_completeness: Optional[float] = None
    """
    Fraction of scored fields that are populated, 0.0–1.0. Computed externally
    or by calling compute_completeness(). Used to weight match confidence.
    """

    def compute_completeness(self) -> float:
        """
        Calculate what fraction of the key scoring fields are populated.
        Stores the result in profile_completeness and returns it.

        Fields counted: years_experience, seniority, skills (non-empty),
        languages (non-empty), preferred_locations (non-empty),
        nationality_status (not UNKNOWN).
        """
        scored_fields = [
            self.years_experience is not None,
            self.seniority is not None,
            len(self.skills) > 0,
            len(self.languages) > 0,
            len(self.preferred_locations) > 0,
            self.nationality_status != NationalityStatus.UNKNOWN,
        ]
        self.profile_completeness = sum(scored_fields) / len(scored_fields)
        return self.profile_completeness

    @property
    def all_skills(self) -> list[str]:
        """Combined deduplicated list of skills and certifications."""
        return list(dict.fromkeys(self.skills + self.certifications))


# ---------------------------------------------------------------------------
# MatchExplanation
# ---------------------------------------------------------------------------

@dataclass
class ComponentScore:
    """Score and explanation for a single scoring factor."""
    factor: str
    """Name of the scoring factor (e.g. 'skill_overlap', 'seniority_alignment')."""

    score: float
    """Raw score for this factor, 0.0–1.0."""

    weight: float
    """Weight applied to this factor in the total score, 0.0–1.0."""

    weighted_score: float
    """score * weight. Pre-computed for transparency."""

    confidence: ConfidenceLevel
    """Data quality confidence for this component."""

    detail: str
    """One sentence explaining what was compared and what was found."""


@dataclass
class MatchExplanation:
    """
    Structured human-readable breakdown of a match result.

    Every field here corresponds to something deterministically derived from
    the candidate profile and job posting. Nothing is inferred or estimated
    beyond what the data directly supports.
    """

    # --- Component breakdown ---
    components: list[ComponentScore] = field(default_factory=list)
    """One ComponentScore per scoring factor. Ordered by weighted contribution descending."""

    # --- Narrative sections ---
    strongest_matches: list[str] = field(default_factory=list)
    """Factors where the candidate aligns well with the role."""

    missing_requirements: list[str] = field(default_factory=list)
    """
    Skills or qualifications explicitly required by the posting that are
    absent from the candidate profile. Stated as factual gaps, not judgments.
    """

    red_flags: list[str] = field(default_factory=list)
    """
    Conditions that significantly reduce match viability and are unlikely
    to be bridged by context. Examples: hard Saudization barrier for an
    expatriate, seniority mismatch of more than two bands.
    """

    concerns: list[str] = field(default_factory=list)
    """
    Weaker signals that warrant attention but are not disqualifying.
    Examples: skills listed but with no evidence of recent use, location
    preference mismatch with relocation willingness.
    """

    saudi_observations: list[str] = field(default_factory=list)
    """
    Observations specific to Saudi market context: Tamheer classification,
    Nitaqat implications, Arabic language requirements, HRDF program relevance.
    These are factual observations, not recommendations.
    """

    data_gaps: list[str] = field(default_factory=list)
    """
    Fields that were absent from the candidate profile or job posting and
    reduced confidence in specific scoring components.
    """


# ---------------------------------------------------------------------------
# MatchResult
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    """
    Scored output of a single candidate-job comparison.

    The total_score is normalized to 0–100. All components that contributed
    to it are recorded in explanation.components so the score can be fully
    reconstructed from the inputs. There are no hidden adjustments.
    """

    candidate_id: str
    job_id: str

    total_score: float
    """Weighted aggregate score, 0–100. Higher = stronger match on measured factors."""

    confidence: ConfidenceLevel
    """Overall confidence in the score, derived from data completeness on both sides."""

    explanation: MatchExplanation

    # --- Convenience flags ---
    has_red_flags: bool = False
    """True if explanation.red_flags is non-empty. Surfaced for quick filtering."""

    is_tamheer_role: bool = False
    """True if the job's employment_type is TAMHEER. Surfaced for pipeline routing."""

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON output or display."""
        return {
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "total_score": round(self.total_score, 1),
            "confidence": self.confidence.value,
            "has_red_flags": self.has_red_flags,
            "is_tamheer_role": self.is_tamheer_role,
            "explanation": {
                "components": [
                    {
                        "factor": c.factor,
                        "score": round(c.score, 3),
                        "weight": c.weight,
                        "weighted_score": round(c.weighted_score, 3),
                        "confidence": c.confidence.value,
                        "detail": c.detail,
                    }
                    for c in self.explanation.components
                ],
                "strongest_matches": self.explanation.strongest_matches,
                "missing_requirements": self.explanation.missing_requirements,
                "red_flags": self.explanation.red_flags,
                "concerns": self.explanation.concerns,
                "saudi_observations": self.explanation.saudi_observations,
                "data_gaps": self.explanation.data_gaps,
            },
        }

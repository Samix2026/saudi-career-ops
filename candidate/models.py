"""
Data models for raw candidate input and intermediate pipeline structures.

These types represent candidate data before it reaches the matching engine.
They hold raw (un-normalized) text, structured experience and education records,
and provenance metadata.

Pipeline:
  raw dict
    → parser.parse_candidate()        → RawCandidateInput
    → normalizer + profile_builder    → matching.models.CandidateProfile

Nothing in this module writes to the matching engine's types. Normalization and
assembly happen in normalizer.py and profile_builder.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CandidateExperience:
    """A single work experience entry from a candidate's history."""

    title: str
    """Job title as stated by the candidate. Not normalized."""

    company: Optional[str] = None

    start_year: Optional[int] = None
    end_year: Optional[int] = None
    """None means the position is current or the end date was not stated."""

    is_current: bool = False

    is_training: bool = False
    """True for Tamheer, co-op, or other formal training placements.
    Training entries are excluded from professional years-of-experience totals."""

    description: Optional[str] = None


@dataclass
class CandidateEducation:
    """A single education record."""

    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    graduation_year: Optional[int] = None

    is_current: bool = False
    """True if the candidate is currently enrolled. Used to hint COOP eligibility."""


@dataclass
class CandidateCertification:
    """A professional certification."""

    name: str
    """Certification name as provided. Taxonomy normalization happens in normalizer.py."""

    issuer: Optional[str] = None
    year: Optional[int] = None


@dataclass
class CandidateLanguage:
    """A language the candidate works in, with optional self-reported proficiency."""

    language: str
    """Raw label: 'Arabic', 'العربية', 'English', 'en', 'إنجليزي', etc."""

    proficiency: Optional[str] = None
    """Self-reported level: 'native', 'fluent', 'professional', 'conversational', 'basic'."""


@dataclass
class CandidateProfileMetadata:
    """Provenance and ingestion metadata attached to a parsed profile."""

    source: str
    """How this profile was created: 'manual_form', 'cv_upload', 'api', 'test'."""

    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    raw_input_hash: Optional[str] = None
    """SHA-256 hex digest of the original input dict. Used for deduplication."""

    notes: Optional[str] = None


@dataclass
class RawCandidateInput:
    """
    Structured container for a candidate's raw (un-normalized) profile data.

    Produced by parser.parse_candidate() from a raw dict. Consumed by
    normalizer.py and profile_builder.py. All original text values are
    preserved; the full source dict is retained in .raw for auditing.

    Fields beyond id are optional. Absent fields produce None or empty lists —
    they do not raise errors downstream. Sparse profiles produce lower-confidence
    match scores, not pipeline failures.
    """

    id: str
    """Stable identifier. Opaque to the matching engine."""

    # --- Identity ---
    name: Optional[str] = None
    """Display name in Latin script."""

    name_arabic: Optional[str] = None
    """Display name in Arabic script, if provided separately."""

    # --- Skills (raw text, pre-normalization) ---
    raw_skills: list[str] = field(default_factory=list)
    """Skill labels exactly as typed. Taxonomy resolution happens in normalizer.py."""

    # --- Certifications ---
    certifications: list[CandidateCertification] = field(default_factory=list)

    # --- Languages (raw labels, pre-normalization) ---
    raw_languages: list[CandidateLanguage] = field(default_factory=list)

    # --- Location ---
    preferred_locations: list[str] = field(default_factory=list)
    """Location strings as provided: 'Riyadh', 'الرياض', 'Remote', etc."""

    willing_to_relocate: Optional[bool] = None
    """None = not stated. False = stated preference to stay. True = open to relocation."""

    # --- Employment preferences (raw labels) ---
    raw_employment_preferences: list[str] = field(default_factory=list)

    # --- Nationality ---
    nationality_status: Optional[str] = None
    """Raw string: 'saudi_national', 'expatriate', 'سعودي', etc."""

    # --- Saudi program eligibility (raw labels) ---
    raw_saudi_program_eligibility: list[str] = field(default_factory=list)

    # --- Career history ---
    experiences: list[CandidateExperience] = field(default_factory=list)
    education: list[CandidateEducation] = field(default_factory=list)

    # --- Explicit overrides (trusted, not inferred) ---
    years_experience_override: Optional[float] = None
    """If the candidate explicitly states total years of experience.
    Overrides the value computed from experience entry dates."""

    seniority_override: Optional[str] = None
    """Candidate's self-reported seniority or title hint (e.g. 'senior', 'mid')."""

    # --- Provenance ---
    metadata: Optional[CandidateProfileMetadata] = None

    raw: dict = field(default_factory=dict, repr=False)
    """Original input dict, preserved for auditing and re-parsing."""

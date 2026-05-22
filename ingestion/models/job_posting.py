"""
Job posting data model for Saudi Career Ops.

Central data contract for all ingested job records, regardless of source.
All connectors normalize their output into this structure before downstream
processing. Fields are optional where source data is genuinely unavailable —
do not substitute guesses for missing values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Language(str, Enum):
    ARABIC = "ar"
    ENGLISH = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TAMHEER = "tamheer"       # Government-sponsored on-the-job training (Saudi-specific)
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    UNKNOWN = "unknown"


class Seniority(str, Enum):
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class SaudiRelevance(str, Enum):
    PRIMARY = "primary"        # Saudi-based role, Saudi employer, or Saudi-national target
    SECONDARY = "secondary"    # Regional role with Saudi component, or multinational with SA office
    PERIPHERAL = "peripheral"  # International role with limited Saudi-specific dimension


@dataclass
class SalaryHint:
    """
    Salary information exactly as stated in the posting.
    No normalization or estimation — preserve what was written.
    """
    raw: str                          # Original text (e.g. "12,000–18,000 SAR/month")
    currency: Optional[str] = None    # Detected currency code (e.g. "SAR", "USD")
    is_estimated: bool = False        # True if this is inferred, not stated


@dataclass
class JobPosting:
    """
    Normalized representation of a single job posting.

    Produced by connector.normalize() after raw data is fetched from a source.
    Consumed by the parsing, matching, and analysis layers.

    All fields that are not derivable from the source should be left as None
    rather than populated with defaults that misrepresent the data.
    """

    # --- Identity ---
    id: str
    """Stable unique identifier. Format: {source_id}:{source-internal-id}"""

    source: str
    """Source registry ID matching an entry in data/saudi-job-sources.json"""

    source_url: Optional[str]
    """Canonical URL for the posting. None if the source has no stable URL."""

    fetched_at: datetime
    """UTC timestamp when this record was retrieved."""

    # --- Core content ---
    title: str
    """Job title as written in the posting. Not normalized."""

    company: str
    """Employer name as stated in the posting."""

    location: str
    """Location string as stated (e.g. 'Riyadh, Saudi Arabia', 'Remote – KSA')."""

    description: str
    """Full job description text, preserving original language and formatting."""

    language: Language = Language.UNKNOWN
    """Detected primary language of the posting content."""

    # --- Classification ---
    employment_type: Optional[EmploymentType] = None
    seniority: Optional[Seniority] = None

    skills: list[str] = field(default_factory=list)
    """
    Skills extracted or inferred from the posting.
    Each entry should be a normalized skill label (e.g. 'Python', 'Project Management').
    Do not include every word — only identifiable, meaningful skill terms.
    """

    # --- Saudi context ---
    saudi_relevance: SaudiRelevance = SaudiRelevance.PRIMARY
    saudization_signal: Optional[str] = None
    """
    Any explicit Saudization or Saudi-national preference language found in the posting.
    Preserve the original phrasing — do not interpret or paraphrase.
    """

    # --- Compensation ---
    salary_hint: Optional[SalaryHint] = None

    # --- Timestamps ---
    posted_at: Optional[datetime] = None
    """When the job was posted, according to the source. None if not stated."""

    expires_at: Optional[datetime] = None
    """When the posting closes, if stated."""

    # --- Metadata ---
    raw: Optional[dict] = field(default=None, repr=False)
    """
    Original unmodified record from the source. Retained for debugging and
    re-parsing without re-fetching. Not included in serialized output by default.
    """

    def to_dict(self, include_raw: bool = False) -> dict:
        """Serialize to a plain dict. Suitable for JSON output."""
        result = {
            "id": self.id,
            "source": self.source,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "language": self.language.value,
            "employment_type": self.employment_type.value if self.employment_type else None,
            "seniority": self.seniority.value if self.seniority else None,
            "skills": self.skills,
            "saudi_relevance": self.saudi_relevance.value,
            "saudization_signal": self.saudization_signal,
            "salary_hint": {
                "raw": self.salary_hint.raw,
                "currency": self.salary_hint.currency,
                "is_estimated": self.salary_hint.is_estimated,
            } if self.salary_hint else None,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
        if include_raw:
            result["raw"] = self.raw
        return result

    @classmethod
    def field_names(cls) -> list[str]:
        """Returns the list of public field names. Useful for schema documentation."""
        import dataclasses
        return [f.name for f in dataclasses.fields(cls) if f.name != "raw"]

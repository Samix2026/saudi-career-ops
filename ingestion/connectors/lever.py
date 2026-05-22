"""
Lever ATS connector — Saudi Career Ops.

ACCESS MODEL
------------
Lever job postings are publicly accessible at:
  https://jobs.lever.co/{company-slug}

A JSON API endpoint is also available for each company's board:
  https://api.lever.co/v0/postings/{company-slug}?mode=json

This is a public, unauthenticated endpoint — Lever intentionally exposes it
to allow companies to embed their job listings externally. It is distinct
from the Lever Partner API, which requires OAuth and employer authorization.

Content is English-primary. Lever is used by tech companies, startups, and
multinational regional HQ entities. Saudi-based companies using Lever exist
but are less common than on LinkedIn or Bayt.

Terms of service: https://www.lever.co/terms-of-service
The public postings endpoint is designed for external consumption, but volume
of requests and acceptable use constraints should be reviewed.

Current status: NOT IMPLEMENTED. fetch_jobs() raises NotImplementedError.
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional

from ingestion.connectors.base import BaseConnector, ConnectorError, SourceMetadata
from ingestion.models.job_posting import (
    EmploymentType,
    JobPosting,
    Language,
    SaudiRelevance,
    Seniority,
)

logger = logging.getLogger(__name__)

# Lever commitment field values mapped to internal EmploymentType.
# Lever uses "commitment" rather than "employment_type" in its schema.
_COMMITMENT_MAP: dict[str, EmploymentType] = {
    "Full-time": EmploymentType.FULL_TIME,
    "Part-time": EmploymentType.PART_TIME,
    "Contract": EmploymentType.CONTRACT,
    "Internship": EmploymentType.INTERNSHIP,
    "Contractor": EmploymentType.CONTRACT,
}

# Lever seniority is not a structured field — it appears in the title or team name.
# This mapping is used by the seniority extraction heuristic in normalize().
_SENIORITY_KEYWORDS: dict[str, Seniority] = {
    "intern": Seniority.ENTRY,
    "junior": Seniority.JUNIOR,
    "mid-level": Seniority.MID,
    "senior": Seniority.SENIOR,
    "staff": Seniority.SENIOR,
    "lead": Seniority.LEAD,
    "principal": Seniority.LEAD,
    "manager": Seniority.MANAGER,
    "director": Seniority.DIRECTOR,
    "vp": Seniority.EXECUTIVE,
    "vice president": Seniority.EXECUTIVE,
    "chief": Seniority.EXECUTIVE,
}


class LeverConnector(BaseConnector):
    """
    Connector for the Lever public postings API.

    Like GreenhouseConnector, this targets a single company slug. Aggregate
    across companies at the caller level.

    Parameters
    ----------
    company_slug:
        The Lever company identifier (e.g. 'neom' for api.lever.co/v0/postings/neom).

    Usage (once implemented):
        connector = LeverConnector(company_slug="example-company")
        for posting in connector.run(location="Saudi Arabia"):
            process(posting)
    """

    _POSTINGS_API = "https://api.lever.co/v0/postings/{slug}?mode=json"
    _POSTING_URL = "https://jobs.lever.co/{slug}/{posting_id}"

    def __init__(self, company_slug: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._slug = company_slug

    @classmethod
    def source_metadata(cls) -> SourceMetadata:
        return SourceMetadata(
            source_id="lever",
            display_name="Lever ATS",
            base_url="https://jobs.lever.co",
            requires_auth=False,
            default_rate_limit_rps=1.0,
            terms_of_service_url="https://www.lever.co/terms-of-service",
            notes=(
                "Public postings endpoint (api.lever.co/v0/postings/{slug}?mode=json) "
                "is designed for external embedding and requires no authentication. "
                "The Lever Partner API is separate and requires employer authorization. "
                "Content is English-primary. Seniority is not a structured field."
            ),
        )

    def fetch_jobs(
        self,
        *,
        location: Optional[str] = None,
        keyword: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Not implemented.

        To implement:
          1. GET https://api.lever.co/v0/postings/{slug}?mode=json
          2. Response is a JSON array of posting objects (no pagination wrapper;
             all postings for the company are returned in a single response).
          3. Filter client-side by location and keyword if provided.
          4. No rate limiting is documented for the public endpoint, but
             the connector's default_rate_limit_rps (1.0 rps) applies.

        Optional server-side filters available as query parameters:
          - ?team={team}        filter by team/department
          - ?location={location} filter by location string (exact match only)
          - ?commitment={type}  filter by commitment type

        Raises
        ------
        NotImplementedError
            Always. This connector has no active implementation.
        """
        raise NotImplementedError(
            f"LeverConnector.fetch_jobs() is not implemented for slug={self._slug!r}."
        )

    def normalize(self, raw: dict) -> JobPosting:
        """
        Not implemented.

        Lever posting object structure (v0 API):
          raw = {
            "id": "abc123-...",
            "text": "Senior Data Engineer",        # job title
            "categories": {
              "team": "Engineering",
              "commitment": "Full-time",
              "location": "Riyadh, Saudi Arabia",
              "department": "Data Platform"
            },
            "tags": ["python", "spark", "arabic"],
            "description": "<p>HTML description...</p>",
            "descriptionPlain": "Plain text description...",
            "lists": [                             # structured sections (requirements, etc.)
              {"text": "Requirements", "content": "<ul>...</ul>"}
            ],
            "additional": "<p>Additional info...</p>",
            "hostedUrl": "https://jobs.lever.co/company/abc123-...",
            "applyUrl": "https://jobs.lever.co/company/abc123-.../apply",
            "createdAt": 1713200000000             # milliseconds since epoch
          }

        Notes on normalization:
          - Prefer `descriptionPlain` over `description` to avoid HTML in description.
          - `createdAt` is milliseconds — divide by 1000 for a Unix timestamp.
          - Seniority is not structured; extract from `text` (title) using keywords.
          - Language must be detected from title + descriptionPlain.
          - `tags` are uncontrolled free-text; filter before adding to skills.
        """
        raise NotImplementedError(
            "LeverConnector.normalize() is not implemented."
        )

    def validate(self, posting: JobPosting) -> list[str]:
        """
        Lever-specific validation:
        - Warn if description contains HTML (descriptionPlain was not used).
        - Warn if source_url does not match expected Lever URL pattern.
        - Warn if seniority is UNKNOWN (title did not contain a recognized keyword).
        """
        issues = []

        if posting.description and "<" in posting.description and ">" in posting.description:
            issues.append("description may contain HTML — ensure descriptionPlain is used in normalize()")

        if posting.source_url and "lever.co" not in posting.source_url:
            issues.append(f"source_url does not look like a Lever URL: {posting.source_url!r}")

        if posting.seniority is None or posting.seniority == Seniority.UNKNOWN:
            issues.append("seniority is UNKNOWN — title keyword extraction found no match")

        return issues

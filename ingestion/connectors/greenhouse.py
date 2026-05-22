"""
Greenhouse ATS connector — Saudi Career Ops.

ACCESS MODEL
------------
Greenhouse job boards are publicly accessible at a predictable URL structure:
  https://boards.greenhouse.io/{company-slug}/jobs

The JSON job board feed is also publicly available:
  https://boards.greenhouse.io/v1/boards/{company-slug}/jobs

This is distinct from the Greenhouse Harvest API, which requires employer
authorization and is used for internal ATS operations (not job discovery).

No authentication is required to read the public job board feed.
Content is predominantly English. Arabic-language postings are uncommon on
Greenhouse-hosted boards but are not impossible.

Terms of service: https://greenhouse.io/terms-of-service
Review before implementation. Greenhouse's ToS addresses automated access;
volume and frequency of requests should be conservative.

Current status: NOT IMPLEMENTED. fetch_jobs() raises NotImplementedError.
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional
from urllib.parse import urljoin

from ingestion.connectors.base import BaseConnector, ConnectorError, SourceMetadata
from ingestion.models.job_posting import (
    EmploymentType,
    JobPosting,
    Language,
    SaudiRelevance,
    Seniority,
)

logger = logging.getLogger(__name__)

# Greenhouse employment type labels as returned by the Jobs API.
# Map to internal EmploymentType enum values.
_EMPLOYMENT_TYPE_MAP: dict[str, EmploymentType] = {
    "Full-time": EmploymentType.FULL_TIME,
    "Part-time": EmploymentType.PART_TIME,
    "Contract": EmploymentType.CONTRACT,
    "Internship": EmploymentType.INTERNSHIP,
    "Temporary": EmploymentType.CONTRACT,
}


class GreenhouseConnector(BaseConnector):
    """
    Connector for the Greenhouse public job board API.

    This connector targets a single company's Greenhouse job board. To collect
    jobs across multiple companies, instantiate one connector per company slug
    and aggregate results at the caller level.

    Parameters
    ----------
    company_slug:
        The Greenhouse board slug for the target company
        (e.g. 'neom' if the board is at boards.greenhouse.io/neom).

    Usage (once implemented):
        connector = GreenhouseConnector(company_slug="neom")
        for posting in connector.run(location="Saudi Arabia"):
            process(posting)
    """

    _JOBS_API_BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    _JOB_DETAIL_URL = "https://boards.greenhouse.io/{slug}/jobs/{job_id}"

    def __init__(self, company_slug: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._slug = company_slug

    @classmethod
    def source_metadata(cls) -> SourceMetadata:
        return SourceMetadata(
            source_id="greenhouse",
            display_name="Greenhouse ATS",
            base_url="https://boards.greenhouse.io",
            requires_auth=False,
            default_rate_limit_rps=1.0,
            terms_of_service_url="https://greenhouse.io/terms-of-service",
            notes=(
                "Public job board feed requires no authentication. "
                "The Harvest API (internal ATS operations) is separate and requires "
                "employer authorization — this connector does not use it. "
                "Content is predominantly English."
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
          1. GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
          2. Parse the JSON response: {"jobs": [...], "meta": {...}}
          3. Each job object contains: id, title, location, content (HTML description),
             updated_at, absolute_url, departments, offices, metadata
          4. Filter by location string client-side (Greenhouse API has limited
             server-side location filtering).
          5. Apply rate limiting between paginated requests if the company has
             more than one page of jobs (rare but possible).

        The `content=true` parameter includes the full job description. Without it,
        a second request per job is needed to retrieve the description.

        Raises
        ------
        NotImplementedError
            Always. This connector has no active implementation.
        """
        raise NotImplementedError(
            f"GreenhouseConnector.fetch_jobs() is not implemented for slug={self._slug!r}."
        )

    def normalize(self, raw: dict) -> JobPosting:
        """
        Not implemented.

        Greenhouse API response structure (subject to API version):
          raw = {
            "id": 12345,
            "title": "Senior Product Manager",
            "location": {"name": "Riyadh, Saudi Arabia"},
            "content": "<p>HTML job description...</p>",
            "updated_at": "2026-04-15T09:00:00.000Z",
            "absolute_url": "https://boards.greenhouse.io/neom/jobs/12345",
            "departments": [{"name": "Technology"}],
            "offices": [{"name": "Riyadh"}],
            "metadata": [{"id": 1, "name": "Employment Type", "value": "Full-time"}]
          }

        Notes on normalization:
          - Strip HTML from `content` before storing in description.
          - Employment type is often in `metadata` rather than a top-level field.
          - `updated_at` is not the same as `posted_at`; Greenhouse does not always
            expose the original post date via the public API.
          - Language detection must be applied to title + stripped description.
        """
        raise NotImplementedError(
            "GreenhouseConnector.normalize() is not implemented."
        )

    def validate(self, posting: JobPosting) -> list[str]:
        """
        Greenhouse-specific validation:
        - Warn if description appears to contain unstripped HTML tags.
        - Warn if source_url does not match the expected Greenhouse URL pattern.
        - Warn if posted_at is missing (Greenhouse public API often omits it).
        """
        issues = []

        if posting.description and "<" in posting.description and ">" in posting.description:
            issues.append("description may contain unstripped HTML — review normalize()")

        if posting.source_url and "greenhouse.io" not in posting.source_url:
            issues.append(f"source_url does not look like a Greenhouse URL: {posting.source_url!r}")

        if posting.posted_at is None:
            issues.append(
                "posted_at is missing — Greenhouse public API does not reliably expose original post date"
            )

        return issues

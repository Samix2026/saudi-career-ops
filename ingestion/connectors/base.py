"""
Abstract base connector for Saudi Career Ops job ingestion.

All source-specific connectors must inherit from BaseConnector and implement
the three abstract methods: fetch_jobs(), normalize(), and validate().

Design constraints:
- Connectors are read-only. They retrieve data; they do not submit, modify,
  or interact with job postings on behalf of any user.
- Each connector is responsible for respecting its source's rate limits,
  terms of service, and access requirements.
- Raw records are normalized into JobPosting objects before leaving the connector.
  Downstream layers never see source-specific data structures.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

from ingestion.models.job_posting import JobPosting

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceMetadata:
    """
    Static descriptor for a connector's data source.
    Values here should match the corresponding entry in data/saudi-job-sources.json.
    """
    source_id: str
    """Registry ID from data/saudi-job-sources.json."""

    display_name: str
    """Human-readable name used in logs and error messages."""

    base_url: Optional[str]
    """Root URL of the source. None for sources with no unified URL (e.g. Taleo)."""

    requires_auth: bool
    """Whether the source requires an authenticated session to access job listings."""

    default_rate_limit_rps: float
    """
    Default maximum requests per second this connector will issue.
    Connectors must not exceed this without explicit operator override.
    This is a courtesy limit — it does not guarantee compliance with the
    source's actual rate limit policy.
    """

    terms_of_service_url: Optional[str]
    """URL of the source's ToS, for reference during connector review."""

    notes: str = ""
    """Any access or legal constraints relevant to this source."""


class RateLimiter:
    """
    Simple token-based rate limiter. Enforces a minimum interval between calls.

    This is a best-effort implementation suitable for single-process use.
    It does not coordinate across multiple processes or threads. For
    distributed ingestion, replace with a shared rate limiter (e.g., Redis-backed).
    """

    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self._min_interval: float = 1.0 / requests_per_second
        self._last_called: float = 0.0

    def wait(self) -> None:
        """Block until the next request is permitted."""
        now = time.monotonic()
        elapsed = now - self._last_called
        wait_for = self._min_interval - elapsed
        if wait_for > 0:
            logger.debug("Rate limiter sleeping %.3fs", wait_for)
            time.sleep(wait_for)
        self._last_called = time.monotonic()

    @property
    def requests_per_second(self) -> float:
        return 1.0 / self._min_interval


class ConnectorError(Exception):
    """Raised when a connector encounters a non-recoverable error."""


class AuthenticationError(ConnectorError):
    """Raised when the connector cannot authenticate with the source."""


class RateLimitExceeded(ConnectorError):
    """Raised when the source returns a rate limit response (e.g. HTTP 429)."""


class BaseConnector(ABC):
    """
    Abstract base class for all job source connectors.

    Subclasses must implement:
      - fetch_jobs()  — retrieve raw records from the source
      - normalize()   — convert a raw record to a JobPosting
      - validate()    — verify a normalized JobPosting is structurally sound

    Subclasses should not override __init__ without calling super().__init__().
    """

    def __init__(self, rate_limit_rps: Optional[float] = None) -> None:
        meta = self.source_metadata()
        rps = rate_limit_rps if rate_limit_rps is not None else meta.default_rate_limit_rps
        self._rate_limiter = RateLimiter(rps)
        self._logger = logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

    # ------------------------------------------------------------------
    # Abstract interface — must be implemented by each connector
    # ------------------------------------------------------------------

    @classmethod
    @abstractmethod
    def source_metadata(cls) -> SourceMetadata:
        """
        Return the static descriptor for this connector's source.
        Must be a classmethod so metadata is accessible without instantiation.
        """

    @abstractmethod
    def fetch_jobs(
        self,
        *,
        location: Optional[str] = None,
        keyword: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Retrieve raw job records from the source.

        Yields raw records as dicts — one per job posting, in source-native
        structure. No normalization or filtering is applied here.

        Parameters
        ----------
        location:
            Filter by location string (e.g. 'Saudi Arabia', 'Riyadh').
            Interpretation is source-specific.
        keyword:
            Filter by keyword or job title. Interpretation is source-specific.
        max_results:
            Maximum number of records to yield. None means no limit.

        Yields
        ------
        dict
            A single raw record from the source. Structure varies by source.

        Raises
        ------
        AuthenticationError
            If the source requires authentication and credentials are missing
            or invalid.
        RateLimitExceeded
            If the source returns a rate-limit response.
        ConnectorError
            For any other non-recoverable error during fetch.
        """

    @abstractmethod
    def normalize(self, raw: dict) -> JobPosting:
        """
        Convert a raw record from fetch_jobs() into a normalized JobPosting.

        Must not make network requests. Must not modify the raw dict.
        Must return a JobPosting with at minimum: id, source, fetched_at,
        title, company, location, description populated.

        Parameters
        ----------
        raw:
            A single dict as yielded by fetch_jobs().

        Returns
        -------
        JobPosting
            A normalized job posting. Optional fields should be None if
            not available in the source data — do not estimate or fabricate.

        Raises
        ------
        ValueError
            If the raw record is missing required fields or is structurally invalid.
        """

    @abstractmethod
    def validate(self, posting: JobPosting) -> list[str]:
        """
        Check a normalized JobPosting for structural completeness.

        Returns a list of validation messages. An empty list means the record
        is valid. Messages should describe what is missing or malformed — they
        are used for logging and data quality tracking, not raised as exceptions.

        This method should not re-fetch or re-normalize. It operates only on
        the JobPosting it receives.

        Parameters
        ----------
        posting:
            A JobPosting produced by normalize().

        Returns
        -------
        list[str]
            Validation messages. Empty list if the posting passes all checks.
        """

    # ------------------------------------------------------------------
    # Concrete helpers available to all connectors
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        location: Optional[str] = None,
        keyword: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[JobPosting]:
        """
        Full ingestion pipeline: fetch → normalize → validate → yield.

        Applies rate limiting between fetches. Logs validation warnings.
        Skips records that fail normalization rather than halting the run.

        Yields valid, normalized JobPosting objects.
        """
        meta = self.source_metadata()
        self._logger.info(
            "Starting ingestion run: source=%s location=%r keyword=%r max_results=%s",
            meta.source_id, location, keyword, max_results,
        )

        yielded = 0
        for raw in self.fetch_jobs(location=location, keyword=keyword, max_results=max_results):
            self._rate_limiter.wait()

            try:
                posting = self.normalize(raw)
            except (ValueError, KeyError) as exc:
                self._logger.warning("normalize() failed, skipping record: %s", exc)
                continue

            issues = self.validate(posting)
            if issues:
                self._logger.warning(
                    "Validation issues for posting %s: %s",
                    posting.id, "; ".join(issues),
                )

            yield posting
            yielded += 1

            if max_results is not None and yielded >= max_results:
                break

        self._logger.info("Ingestion run complete: %d records yielded", yielded)

    def _now(self) -> datetime:
        """Current UTC time. Extracted for testability."""
        return datetime.utcnow()

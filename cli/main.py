"""
Saudi Career Ops — command-line interface.

Entry point: python3 -m cli.main <command> [options]

Commands
--------
match   Compare one or more candidate profiles against one or more job postings.

        python3 -m cli.main match \\
            --candidate data/sample-candidate-profiles.json \\
            --job ingestion/output/sample-output.json

        Each candidate is compared to each job. Results are printed in order
        of descending score within each candidate.

Options
-------
--json      Reserved. JSON output is not yet implemented; text output is shown.
--verbose   Print component-level score breakdown in addition to the summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Path bootstrap — allows running from the repo root without installing.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingestion.models.job_posting import (
    EmploymentType,
    JobPosting,
    Language,
    SalaryHint,
    SaudiRelevance,
    Seniority,
)
from ingestion.parsers.job_parser import enrich
from candidate.parser import parse_candidate
from candidate.profile_builder import build_profile
from matching.models import CandidateProfile, MatchResult
from matching.scorer import Scorer


# ---------------------------------------------------------------------------
# Terminal formatting constants
# ---------------------------------------------------------------------------

_WIDTH = 62
_RULE  = "─" * _WIDTH
_THICK = "━" * _WIDTH


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> object:
    """Load and parse a JSON file. Exit with a clear message on any failure."""
    if not path.exists():
        _die(f"File not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        _die(f"Invalid JSON in {path}: {exc}")


def _load_candidates(path: Path) -> list[CandidateProfile]:
    """
    Load candidate profiles from a JSON file.

    Accepts:
      - {"candidates": [...]}  — array under a key (standard format)
      - [...]                  — bare array
      - {...}                  — single candidate object
    """
    data = _load_json(path)

    if isinstance(data, dict) and "candidates" in data:
        records = data["candidates"]
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        _die(f"Cannot interpret candidate file: {path}")

    profiles: list[CandidateProfile] = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            _warn(f"Skipping candidate record {i}: not a dict")
            continue
        if record.get("id", "").startswith("_"):
            continue  # skip metadata entries
        try:
            raw = parse_candidate(record, source="cli")
            profile = build_profile(raw)
            profiles.append(profile)
        except Exception as exc:  # noqa: BLE001
            _warn(f"Skipping candidate record {i} ({record.get('id', '?')}): {exc}")

    if not profiles:
        _die(f"No valid candidate profiles found in {path}")

    return profiles


def _job_from_dict(record: dict) -> JobPosting:
    """Deserialize one JSON record into a JobPosting, then enrich it."""

    def _dt(val: Optional[str]) -> Optional[datetime]:
        if not val:
            return None
        return datetime.fromisoformat(val.replace("Z", "+00:00"))

    def _salary(val: Optional[dict]) -> Optional[SalaryHint]:
        if not val:
            return None
        return SalaryHint(
            raw=val.get("raw", ""),
            currency=val.get("currency"),
            is_estimated=bool(val.get("is_estimated", False)),
        )

    posting = JobPosting(
        id=str(record.get("id") or ""),
        source=str(record.get("source") or "unknown"),
        source_url=record.get("source_url"),
        fetched_at=_dt(record.get("fetched_at")) or datetime.now(tz=timezone.utc),
        title=str(record.get("title") or ""),
        company=str(record.get("company") or ""),
        location=str(record.get("location") or ""),
        description=str(record.get("description") or ""),
        language=_enum_or(Language, record.get("language"), Language.UNKNOWN),
        employment_type=_enum_or(EmploymentType, record.get("employment_type"), None),
        seniority=_enum_or(Seniority, record.get("seniority"), None),
        skills=list(record.get("skills") or []),
        saudi_relevance=_enum_or(SaudiRelevance, record.get("saudi_relevance"), SaudiRelevance.PRIMARY),
        saudization_signal=record.get("saudization_signal"),
        salary_hint=_salary(record.get("salary_hint")),
        posted_at=_dt(record.get("posted_at")),
        expires_at=_dt(record.get("expires_at")),
    )
    return enrich(posting)


def _load_jobs(path: Path) -> list[JobPosting]:
    """
    Load job postings from a JSON file.

    Accepts:
      - {"records": [...]}  — array under a key (standard ingestion output format)
      - [...]               — bare array
      - {...}               — single job object
    """
    data = _load_json(path)

    if isinstance(data, dict) and "records" in data:
        records = data["records"]
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        _die(f"Cannot interpret job file: {path}")

    jobs: list[JobPosting] = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            _warn(f"Skipping job record {i}: not a dict")
            continue
        if str(record.get("id", "")).startswith("_"):
            continue  # skip metadata entries
        try:
            jobs.append(_job_from_dict(record))
        except Exception as exc:  # noqa: BLE001
            _warn(f"Skipping job record {i} ({record.get('id', '?')}): {exc}")

    if not jobs:
        _die(f"No valid job postings found in {path}")

    return jobs


def _enum_or(enum_cls, value, default):
    """Coerce a string to an enum value, returning default on failure."""
    if not value:
        return default
    try:
        return enum_cls(str(value))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _section(title: str, items: list[str], marker: str) -> None:
    """Print a labelled section with a per-item prefix marker."""
    print(f"\n{title}")
    if items:
        for item in items:
            print(f"  {marker} {item}")
    else:
        print("  (none)")


def _print_match(
    result: MatchResult,
    candidate: CandidateProfile,
    job: JobPosting,
    index: int,
    total: int,
    verbose: bool,
) -> None:
    """Print a single match result in readable text format."""
    exp = result.explanation

    score_bar_filled = int(result.total_score / 5)
    score_bar = "█" * score_bar_filled + "░" * (20 - score_bar_filled)

    flag_note = "  ⚑ has red flags" if result.has_red_flags else ""
    tamheer_note = "  ◆ Tamheer role" if result.is_tamheer_role else ""

    print()
    print(_THICK)
    print(f"Match {index} of {total}")
    print(_RULE)
    print(f"  Candidate  {candidate.name or candidate.id}  [{candidate.id}]")
    print(f"  Job        {job.title}")
    print(f"             {job.company}  ·  {job.location}")
    print(_RULE)
    print(f"  Score      {result.total_score:.1f} / 100   [{score_bar}]")
    print(f"  Confidence {result.confidence.value}{flag_note}{tamheer_note}")
    print(_THICK)

    if verbose and exp.components:
        print("\nScore breakdown")
        for c in exp.components:
            bar = "▪" * int(c.score * 10)
            print(f"  {c.factor:<26} {c.score:.2f}  {bar}")
            print(f"    {c.detail}")

    _section("Strongest matches",      exp.strongest_matches,      "+")
    _section("Missing requirements",   exp.missing_requirements,   "–")
    _section("Red flags",              exp.red_flags,              "!")
    _section("Concerns",               exp.concerns,               "~")
    _section("Saudi observations",     exp.saudi_observations,     "·")

    if exp.data_gaps:
        _section("Data gaps", exp.data_gaps, "?")


def _print_summary(results: list[tuple[CandidateProfile, JobPosting, MatchResult]]) -> None:
    """Print a compact summary table after all detailed results."""
    print()
    print(_THICK)
    print("Summary")
    print(_RULE)
    print(f"  {'Score':>5}   {'Conf':<6}  {'Candidate':<24}  Job")
    print(f"  {'─'*5}   {'─'*6}  {'─'*24}  {'─'*20}")
    for candidate, job, result in sorted(results, key=lambda r: r[2].total_score, reverse=True):
        cname = (candidate.name or candidate.id)[:23]
        jtitle = job.title[:30]
        flag = " !" if result.has_red_flags else ""
        print(
            f"  {result.total_score:>5.1f}   {result.confidence.value:<6}"
            f"  {cname:<24}  {jtitle}{flag}"
        )
    print(_THICK)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_match(args: argparse.Namespace) -> None:
    if args.json:
        _warn("--json output is not yet implemented; displaying text output.")

    candidate_path = Path(args.candidate)
    job_path = Path(args.job)

    candidates = _load_candidates(candidate_path)
    jobs = _load_jobs(job_path)

    scorer = Scorer()
    all_results: list[tuple[CandidateProfile, JobPosting, MatchResult]] = []

    total = len(candidates) * len(jobs)
    index = 0

    for candidate in candidates:
        for job in jobs:
            index += 1
            result = scorer.score(candidate, job)
            all_results.append((candidate, job, result))
            _print_match(result, candidate, job, index, total, verbose=args.verbose)

    if total > 1:
        _print_summary(all_results)

    print()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m cli.main",
        description="Saudi Career Ops — candidate-job matching CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python3 -m cli.main match \\
      --candidate data/sample-candidate-profiles.json \\
      --job ingestion/output/sample-output.json

  python3 -m cli.main match \\
      --candidate examples/sample-candidate-profile.json \\
      --job ingestion/output/sample-output.json \\
      --verbose
""",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    match_p = sub.add_parser(
        "match",
        help="Compare candidate profile(s) against job posting(s).",
    )
    match_p.add_argument(
        "--candidate",
        required=True,
        metavar="FILE",
        help="JSON file containing one or more candidate profiles.",
    )
    match_p.add_argument(
        "--job",
        required=True,
        metavar="FILE",
        help="JSON file containing one or more job postings.",
    )
    match_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="[reserved] JSON output. Not yet implemented.",
    )
    match_p.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print component-level score breakdown.",
    )
    match_p.set_defaults(func=cmd_match)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

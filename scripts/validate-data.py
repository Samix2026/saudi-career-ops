#!/usr/bin/env python3
"""
Validates data/saudi-job-sources.json against its schema constraints.
Uses only the Python standard library — no external dependencies required.

Usage:
    python scripts/validate-data.py
    python scripts/validate-data.py --data path/to/file.json
    python scripts/validate-data.py --verbose
"""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path


# ---------------------------------------------------------------------------
# Constraint definitions (mirrors data/schemas/saudi-job-sources.schema.json)
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "government_platform",
    "saudi_corporate",
    "pif_ecosystem",
    "global_aggregator",
    "regional_aggregator",
    "ats_platform",
    "consulting",
    "tech_company",
    "startup_ecosystem",
}

VALID_SCRAPING_COMPLEXITY = {"low", "medium", "high", "unknown"}

VALID_SAUDI_RELEVANCE = {"primary", "secondary", "peripheral"}

VALID_STATUS = {"active", "planned", "deprecated", "unverified"}

VALID_LANGUAGES = {"ar", "en"}

REQUIRED_SOURCE_FIELDS = {
    "id",
    "name",
    "category",
    "website",
    "language_support",
    "authentication_required",
    "scraping_complexity",
    "saudi_relevance",
    "status",
    "notes",
}

ALLOWED_SOURCE_FIELDS = REQUIRED_SOURCE_FIELDS  # no additional properties permitted

REQUIRED_METADATA_FIELDS = {
    "version",
    "last_reviewed",
    "maintainer",
    "description",
    "status_values",
    "scraping_complexity_values",
    "saudi_relevance_values",
}

KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class ValidationError:
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message

    def __str__(self):
        return f"  [{self.path}] {self.message}"


def is_valid_uri(value: str) -> bool:
    try:
        result = urllib.parse.urlparse(value)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_metadata(metadata: dict) -> list[ValidationError]:
    errors = []
    path = "metadata"

    if not isinstance(metadata, dict):
        errors.append(ValidationError(path, "must be an object"))
        return errors

    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            errors.append(ValidationError(f"{path}.{field}", "required field missing"))

    if "version" in metadata:
        if not isinstance(metadata["version"], str) or not SEMVER_RE.match(metadata["version"]):
            errors.append(ValidationError(f"{path}.version", f"must be a semantic version string (e.g. 0.1.0), got: {metadata['version']!r}"))

    if "last_reviewed" in metadata:
        if not isinstance(metadata["last_reviewed"], str) or not DATE_RE.match(metadata["last_reviewed"]):
            errors.append(ValidationError(f"{path}.last_reviewed", f"must be an ISO 8601 date string (YYYY-MM-DD), got: {metadata['last_reviewed']!r}"))

    for field in ("maintainer", "description"):
        if field in metadata and (not isinstance(metadata[field], str) or not metadata[field].strip()):
            errors.append(ValidationError(f"{path}.{field}", "must be a non-empty string"))

    for field in ("status_values", "scraping_complexity_values", "saudi_relevance_values"):
        if field in metadata:
            if not isinstance(metadata[field], list) or len(metadata[field]) == 0:
                errors.append(ValidationError(f"{path}.{field}", "must be a non-empty array"))

    return errors


def validate_source(entry: dict, index: int) -> list[ValidationError]:
    errors = []
    label = entry.get("id") or f"index {index}"
    path = f"sources[{label}]"

    if not isinstance(entry, dict):
        errors.append(ValidationError(f"sources[{index}]", "each source must be an object"))
        return errors

    # Required fields
    for field in REQUIRED_SOURCE_FIELDS:
        if field not in entry:
            errors.append(ValidationError(f"{path}.{field}", "required field missing"))

    # No additional properties
    extra = set(entry.keys()) - ALLOWED_SOURCE_FIELDS
    for field in sorted(extra):
        errors.append(ValidationError(f"{path}.{field}", f"unexpected field — not permitted by schema"))

    # id
    if "id" in entry:
        if not isinstance(entry["id"], str) or not KEBAB_CASE_RE.match(entry["id"]):
            errors.append(ValidationError(f"{path}.id", f"must be lowercase kebab-case, got: {entry['id']!r}"))

    # name
    if "name" in entry:
        if not isinstance(entry["name"], str) or not entry["name"].strip():
            errors.append(ValidationError(f"{path}.name", "must be a non-empty string"))

    # category
    if "category" in entry:
        if entry["category"] not in VALID_CATEGORIES:
            errors.append(ValidationError(f"{path}.category", f"must be one of {sorted(VALID_CATEGORIES)}, got: {entry['category']!r}"))

    # website
    if "website" in entry:
        w = entry["website"]
        if w is not None:
            if not isinstance(w, str):
                errors.append(ValidationError(f"{path}.website", "must be a URI string or null"))
            elif not is_valid_uri(w):
                errors.append(ValidationError(f"{path}.website", f"must be a valid http/https URI, got: {w!r}"))

    # language_support
    if "language_support" in entry:
        ls = entry["language_support"]
        if not isinstance(ls, list) or len(ls) == 0:
            errors.append(ValidationError(f"{path}.language_support", "must be a non-empty array"))
        else:
            for lang in ls:
                if lang not in VALID_LANGUAGES:
                    errors.append(ValidationError(f"{path}.language_support", f"unsupported language code {lang!r} — valid values: {sorted(VALID_LANGUAGES)}"))
            if len(ls) != len(set(ls)):
                errors.append(ValidationError(f"{path}.language_support", "contains duplicate language codes"))

    # authentication_required
    if "authentication_required" in entry:
        if not isinstance(entry["authentication_required"], bool):
            errors.append(ValidationError(f"{path}.authentication_required", f"must be a boolean, got: {type(entry['authentication_required']).__name__}"))

    # scraping_complexity
    if "scraping_complexity" in entry:
        if entry["scraping_complexity"] not in VALID_SCRAPING_COMPLEXITY:
            errors.append(ValidationError(f"{path}.scraping_complexity", f"must be one of {sorted(VALID_SCRAPING_COMPLEXITY)}, got: {entry['scraping_complexity']!r}"))

    # saudi_relevance
    if "saudi_relevance" in entry:
        if entry["saudi_relevance"] not in VALID_SAUDI_RELEVANCE:
            errors.append(ValidationError(f"{path}.saudi_relevance", f"must be one of {sorted(VALID_SAUDI_RELEVANCE)}, got: {entry['saudi_relevance']!r}"))

    # status
    if "status" in entry:
        if entry["status"] not in VALID_STATUS:
            errors.append(ValidationError(f"{path}.status", f"must be one of {sorted(VALID_STATUS)}, got: {entry['status']!r}"))

    # notes
    if "notes" in entry:
        if not isinstance(entry["notes"], str) or len(entry["notes"].strip()) < 10:
            errors.append(ValidationError(f"{path}.notes", "must be a string of at least 10 characters"))

    return errors


def validate_unique_ids(sources: list) -> list[ValidationError]:
    errors = []
    seen = {}
    for i, entry in enumerate(sources):
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        if entry_id is None:
            continue
        if entry_id in seen:
            errors.append(ValidationError(
                f"sources[{i}].id",
                f"duplicate id {entry_id!r} — first seen at index {seen[entry_id]}"
            ))
        else:
            seen[entry_id] = i
    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate(data_path: Path, verbose: bool) -> bool:
    try:
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: file not found: {data_path}", file=sys.stderr)
        return False
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {data_path}: {exc}", file=sys.stderr)
        return False

    all_errors: list[ValidationError] = []

    # Top-level structure
    if not isinstance(data, dict):
        print("ERROR: root must be a JSON object", file=sys.stderr)
        return False

    if "metadata" not in data:
        all_errors.append(ValidationError("(root)", "required key 'metadata' is missing"))
    else:
        all_errors.extend(validate_metadata(data["metadata"]))

    if "sources" not in data:
        all_errors.append(ValidationError("(root)", "required key 'sources' is missing"))
    else:
        sources = data["sources"]
        if not isinstance(sources, list):
            all_errors.append(ValidationError("sources", "must be an array"))
        elif len(sources) == 0:
            all_errors.append(ValidationError("sources", "must contain at least one entry"))
        else:
            for i, entry in enumerate(sources):
                all_errors.extend(validate_source(entry, i))
            all_errors.extend(validate_unique_ids(sources))

    # Report
    source_count = len(data.get("sources", [])) if isinstance(data.get("sources"), list) else 0

    if all_errors:
        print(f"FAIL  {data_path}")
        print(f"      {len(all_errors)} error(s) found across {source_count} entries:\n")
        for err in all_errors:
            print(err)
        print()
        return False

    if verbose:
        print(f"OK    {data_path}")
        print(f"      {source_count} entries validated — no errors")
    else:
        print(f"OK    {data_path}  ({source_count} entries)")

    return True


def main():
    repo_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(
        description="Validate Saudi Career Ops data files against their schema constraints."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=repo_root / "data" / "saudi-job-sources.json",
        help="Path to the data file to validate (default: data/saudi-job-sources.json)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print additional detail on success",
    )
    args = parser.parse_args()

    success = validate(args.data, verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

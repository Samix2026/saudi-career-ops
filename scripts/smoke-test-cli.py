#!/usr/bin/env python3
"""
Smoke tests for the Saudi Career Ops CLI (cli/main.py).

Runs the CLI as a subprocess and verifies exit codes, output content,
and error handling. Tests also exercise the loader functions directly
to check edge-case input handling without subprocess overhead.

Usage:
    python scripts/smoke-test-cli.py           # pass/fail summary
    python scripts/smoke-test-cli.py --verbose # per-check output
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

_verbose = "--verbose" in sys.argv
_passes = 0
_failures = 0
_PYTHON = sys.executable
_REPO = Path(__file__).resolve().parent.parent


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passes, _failures
    if condition:
        _passes += 1
        if _verbose:
            print(f"  PASS  {label}")
    else:
        _failures += 1
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n[{title}]")


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run cli.main as a module and return the completed process."""
    return subprocess.run(
        [_PYTHON, "-m", "cli.main", *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
    )


_SAMPLE_CANDIDATES = str(_REPO / "data" / "sample-candidate-profiles.json")
_SAMPLE_JOBS = str(_REPO / "ingestion" / "output" / "sample-output.json")
_SINGLE_CANDIDATE = str(_REPO / "examples" / "sample-candidate-profile.json")


# ---------------------------------------------------------------------------
# 1. Basic match invocation
#    Two candidates × two jobs = four results plus a summary table.
# ---------------------------------------------------------------------------

def test_basic_match():
    section("Basic match invocation")

    result = run_cli("match", "--candidate", _SAMPLE_CANDIDATES, "--job", _SAMPLE_JOBS)

    check("exits 0", result.returncode == 0,
          f"stderr: {result.stderr.strip()[:200]}")
    check("stdout is non-empty", len(result.stdout.strip()) > 0)
    check("shows Match 1 of 4", "Match 1 of 4" in result.stdout)
    check("shows Match 4 of 4", "Match 4 of 4" in result.stdout)
    check("shows Summary section", "Summary" in result.stdout)

    # Both candidate names appear
    check("Nora Al-Harbi appears", "Nora Al-Harbi" in result.stdout)
    check("David Chen appears", "David Chen" in result.stdout)

    # Both job titles appear
    check("Arabic job title appears", "مدير مشاريع" in result.stdout)
    check("English job title appears", "Senior Cloud Infrastructure Engineer" in result.stdout)

    # Score fields are present
    check("Score line present", "Score" in result.stdout)
    check("Confidence line present", "Confidence" in result.stdout)

    # Section headers
    check("Strongest matches section", "Strongest matches" in result.stdout)
    check("Missing requirements section", "Missing requirements" in result.stdout)
    check("Red flags section", "Red flags" in result.stdout)
    check("Concerns section", "Concerns" in result.stdout)
    check("Saudi observations section", "Saudi observations" in result.stdout)


# ---------------------------------------------------------------------------
# 2. Verbose flag
#    --verbose adds a Score breakdown block with factor names.
# ---------------------------------------------------------------------------

def test_verbose_flag():
    section("--verbose flag")

    result = run_cli(
        "match",
        "--candidate", _SAMPLE_CANDIDATES,
        "--job", _SAMPLE_JOBS,
        "--verbose",
    )

    check("exits 0 with --verbose", result.returncode == 0,
          result.stderr.strip()[:200])
    check("Score breakdown section present", "Score breakdown" in result.stdout)
    check("skill_overlap factor shown", "skill_overlap" in result.stdout)
    check("seniority_alignment factor shown", "seniority_alignment" in result.stdout)
    check("language factor shown", "language" in result.stdout)


# ---------------------------------------------------------------------------
# 3. JSON placeholder
#    --json triggers a warning message and still shows text output.
# ---------------------------------------------------------------------------

def test_json_placeholder():
    section("--json placeholder")

    result = run_cli(
        "match",
        "--candidate", _SAMPLE_CANDIDATES,
        "--job", _SAMPLE_JOBS,
        "--json",
    )

    check("exits 0 with --json", result.returncode == 0,
          result.stderr.strip()[:200])
    check("--json warning appears in stderr", "not yet implemented" in result.stderr)
    check("text output still produced", "Score" in result.stdout)


# ---------------------------------------------------------------------------
# 4. Single candidate file
#    The examples/ profile (single dict, no 'candidates' wrapper) is accepted.
# ---------------------------------------------------------------------------

def test_single_candidate_file():
    section("Single candidate file (no wrapper)")

    result = run_cli(
        "match",
        "--candidate", _SINGLE_CANDIDATE,
        "--job", _SAMPLE_JOBS,
    )

    check("exits 0", result.returncode == 0,
          result.stderr.strip()[:200])
    check("shows Match 1 of 2", "Match 1 of 2" in result.stdout)
    check("shows Match 2 of 2", "Match 2 of 2" in result.stdout)


# ---------------------------------------------------------------------------
# 5. Missing file — exits 1 with a clear error message
# ---------------------------------------------------------------------------

def test_missing_files():
    section("Missing file error handling")

    result = run_cli("match", "--candidate", "no_such_file.json", "--job", _SAMPLE_JOBS)
    check("missing candidate exits 1", result.returncode == 1)
    check("missing candidate error on stderr",
          "File not found" in result.stderr or "error" in result.stderr.lower())

    result = run_cli("match", "--candidate", _SAMPLE_CANDIDATES, "--job", "no_such_job.json")
    check("missing job exits 1", result.returncode == 1)
    check("missing job error on stderr",
          "File not found" in result.stderr or "error" in result.stderr.lower())


# ---------------------------------------------------------------------------
# 6. Invalid JSON — exits 1 with a clear error message
# ---------------------------------------------------------------------------

def test_invalid_json():
    section("Invalid JSON error handling")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("this is not json {{{")
        bad_path = f.name

    result = run_cli("match", "--candidate", bad_path, "--job", _SAMPLE_JOBS)
    check("invalid JSON exits 1", result.returncode == 1)
    check("invalid JSON error on stderr",
          "Invalid JSON" in result.stderr or "error" in result.stderr.lower())

    Path(bad_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 7. Loader unit tests (direct import, no subprocess)
#    Verify _load_candidates and _load_jobs handle the three input shapes.
# ---------------------------------------------------------------------------

def test_loader_input_shapes():
    section("Loader input shape handling")

    from cli.main import _load_candidates, _load_jobs

    # Candidates: {"candidates": [...]} format
    profiles = _load_candidates(Path(_SAMPLE_CANDIDATES))
    check("candidates-key format loads", len(profiles) == 2,
          f"got {len(profiles)}")

    # Candidates: single dict (no wrapper)
    profiles_single = _load_candidates(Path(_SINGLE_CANDIDATE))
    check("single-dict candidate loads", len(profiles_single) == 1,
          f"got {len(profiles_single)}")

    # Candidates: bare list written to a temp file
    sample_raw = json.loads(Path(_SAMPLE_CANDIDATES).read_text(encoding="utf-8"))
    bare_list = sample_raw["candidates"]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(bare_list, f)
        bare_path = Path(f.name)
    profiles_bare = _load_candidates(bare_path)
    check("bare-list candidate format loads", len(profiles_bare) == 2,
          f"got {len(profiles_bare)}")
    bare_path.unlink(missing_ok=True)

    # Jobs: {"records": [...]} format
    jobs = _load_jobs(Path(_SAMPLE_JOBS))
    check("records-key format loads", len(jobs) == 2,
          f"got {len(jobs)}")

    # Jobs: bare list
    sample_jobs_raw = json.loads(Path(_SAMPLE_JOBS).read_text(encoding="utf-8"))
    bare_jobs = sample_jobs_raw["records"]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(bare_jobs, f)
        bare_jobs_path = Path(f.name)
    jobs_bare = _load_jobs(bare_jobs_path)
    check("bare-list job format loads", len(jobs_bare) == 2,
          f"got {len(jobs_bare)}")
    bare_jobs_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 8. Score integrity
#    Scores are numeric, in range, and deterministic across two runs.
# ---------------------------------------------------------------------------

def test_score_integrity():
    section("Score integrity")

    from cli.main import _load_candidates, _load_jobs
    from matching.scorer import Scorer

    candidates = _load_candidates(Path(_SAMPLE_CANDIDATES))
    jobs = _load_jobs(Path(_SAMPLE_JOBS))
    scorer = Scorer()

    scores_run1 = []
    scores_run2 = []

    for candidate in candidates:
        for job in jobs:
            r1 = scorer.score(candidate, job)
            r2 = scorer.score(candidate, job)
            scores_run1.append(r1.total_score)
            scores_run2.append(r2.total_score)

            check(
                f"score in range 0–100 ({candidate.id} vs {job.id})",
                0.0 <= r1.total_score <= 100.0,
                f"got {r1.total_score}",
            )

    check("scores are deterministic", scores_run1 == scores_run2,
          f"run1={scores_run1}, run2={scores_run2}")
    check("four results produced", len(scores_run1) == 4,
          f"got {len(scores_run1)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_basic_match()
    test_verbose_flag()
    test_json_placeholder()
    test_single_candidate_file()
    test_missing_files()
    test_invalid_json()
    test_loader_input_shapes()
    test_score_integrity()

    print(f"\n{'=' * 40}")
    print(f"  {_passes} passed, {_failures} failed")
    print(f"{'=' * 40}")

    sys.exit(0 if _failures == 0 else 1)

"""
Job parsing pipeline — Saudi Career Ops.

Transforms a raw JobPosting (as produced by a connector's normalize()) into
a more fully analyzed record by extracting structured signals from free text.

Design notes:
- Each parsing function is independent. They do not call each other.
  The pipeline() function sequences them in the correct order.
- Parsing functions must not mutate the input posting. They return new values
  that the caller applies to a copy or new instance.
- All functions are placeholders. The structure is intended to be filled in
  with real implementations per component without redesigning the interface.
- Saudi-specific extraction logic (Saudization signals, Tamheer detection,
  PIF tagging) is intentionally separated into a dedicated module:
  saudi_intel.py (not yet implemented).
"""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import Optional

from ingestion.models.job_posting import (
    JobPosting,
    Language,
    Seniority,
    EmploymentType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Arabic character range (Unicode block: U+0600–U+06FF)
# Used for language detection heuristic.
# ---------------------------------------------------------------------------
_ARABIC_CHAR_RE = re.compile(r"[؀-ۿ]")

# ---------------------------------------------------------------------------
# Seniority keyword map.
# Keys are lowercase; values are Seniority enum members.
# Order matters for regex priority — more specific patterns should appear first.
# ---------------------------------------------------------------------------
_SENIORITY_PATTERNS: list[tuple[re.Pattern, Seniority]] = [
    (re.compile(r"\bchief\b|\bcxo\b|\bceo\b|\bcto\b|\bcfo\b|\bcoo\b", re.I), Seniority.EXECUTIVE),
    (re.compile(r"\bvice president\b|\bvp\b", re.I), Seniority.EXECUTIVE),
    (re.compile(r"\bdirector\b", re.I), Seniority.DIRECTOR),
    (re.compile(r"\bmanager\b|\bhead of\b|\bhead,\b", re.I), Seniority.MANAGER),
    (re.compile(r"\bprincipal\b|\bstaff\b|\blead\b", re.I), Seniority.LEAD),
    (re.compile(r"\bsenior\b|\bsr\.\b", re.I), Seniority.SENIOR),
    (re.compile(r"\bmid.level\b|\bmiddle\b", re.I), Seniority.MID),
    (re.compile(r"\bjunior\b|\bjr\.\b", re.I), Seniority.JUNIOR),
    (re.compile(r"\bintern\b|\btrainee\b|\btamheer\b", re.I), Seniority.ENTRY),
]

# ---------------------------------------------------------------------------
# Employment type signals.
# ---------------------------------------------------------------------------
_EMPLOYMENT_TYPE_PATTERNS: list[tuple[re.Pattern, EmploymentType]] = [
    (re.compile(r"\btamheer\b", re.I), EmploymentType.TAMHEER),
    (re.compile(r"\binternship\b|\bمتدرب\b|\bتدريب\b", re.I | re.U), EmploymentType.INTERNSHIP),
    (re.compile(r"\bpart.time\b|\bدوام جزئي\b", re.I | re.U), EmploymentType.PART_TIME),
    (re.compile(r"\bcontract\b|\bfreelance\b|\bمستقل\b", re.I | re.U), EmploymentType.CONTRACT),
    (re.compile(r"\bfull.time\b|\bدوام كامل\b", re.I | re.U), EmploymentType.FULL_TIME),
]

# ---------------------------------------------------------------------------
# Salary hint patterns.
# ---------------------------------------------------------------------------
_SALARY_PATTERN = re.compile(
    r"(?P<amount>[\d,،]+\s*[-–]\s*[\d,،]+|\d[\d,،]*)"
    r"\s*"
    r"(?P<currency>SAR|USD|EUR|GBP|ريال|ر\.س)",
    re.I | re.U,
)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def detect_language(text: str) -> Language:
    """
    Detect whether text is Arabic, English, or mixed.

    Heuristic: if more than 20% of the word characters are Arabic script,
    the text is considered Arabic. If some Arabic is present but less than 20%,
    it is marked as mixed. Otherwise, English.

    This is a placeholder heuristic. A production implementation should use
    a proper language detection library (e.g. langdetect, fasttext, or the
    Arabic-specific CAMeL Tools tokenizer) with a calibrated threshold.

    Parameters
    ----------
    text:
        The text to analyze. Should be the title + description combined for
        best accuracy.

    Returns
    -------
    Language
        Detected language enum value.
    """
    if not text or not text.strip():
        return Language.UNKNOWN

    # Count word characters (letters) to avoid counting punctuation and whitespace.
    total_chars = len(re.findall(r"\w", text, re.U))
    if total_chars == 0:
        return Language.UNKNOWN

    arabic_chars = len(_ARABIC_CHAR_RE.findall(text))
    arabic_ratio = arabic_chars / total_chars

    # TODO: replace ratio thresholds with a calibrated classifier.
    # Current thresholds are approximate and have not been validated against
    # a labeled corpus of Saudi job postings.
    if arabic_ratio >= 0.5:
        return Language.ARABIC
    elif arabic_ratio >= 0.15:
        return Language.MIXED
    else:
        return Language.ENGLISH


# ---------------------------------------------------------------------------
# Seniority extraction
# ---------------------------------------------------------------------------

def extract_seniority(title: str, description: str = "") -> Optional[Seniority]:
    """
    Extract seniority level from a job title and optionally the description.

    Applies regex patterns in priority order. Returns the first match found
    in the title; if no match, falls back to the description.

    This is a heuristic. Arabic seniority markers are not yet handled —
    that requires a separate Arabic-language extraction pass.

    Parameters
    ----------
    title:
        Job title string.
    description:
        Full job description (optional). Used as fallback if title yields no match.

    Returns
    -------
    Optional[Seniority]
        Matched seniority level, or None if no signal found.
    """
    for pattern, level in _SENIORITY_PATTERNS:
        if pattern.search(title):
            return level

    # Fallback: check description for explicit seniority statements.
    # This is lower confidence — description matches should be flagged.
    for pattern, level in _SENIORITY_PATTERNS:
        if description and pattern.search(description):
            logger.debug("Seniority %s inferred from description (not title)", level.value)
            return level

    return None


# ---------------------------------------------------------------------------
# Employment type extraction
# ---------------------------------------------------------------------------

def extract_employment_type(title: str, description: str = "") -> Optional[EmploymentType]:
    """
    Detect employment type from title and description text.

    Checks for Tamheer first (Saudi-specific employment category that
    must not be conflated with standard internship or contract types).

    Parameters
    ----------
    title:
        Job title string.
    description:
        Full job description.

    Returns
    -------
    Optional[EmploymentType]
        Detected employment type, or None if no signal found.
    """
    combined = f"{title}\n{description}"
    for pattern, emp_type in _EMPLOYMENT_TYPE_PATTERNS:
        if pattern.search(combined):
            return emp_type
    return None


# ---------------------------------------------------------------------------
# Skills extraction
# ---------------------------------------------------------------------------

def extract_skills(title: str, description: str) -> list[str]:
    """
    Extract skill terms from a job posting's text content.

    Placeholder implementation. Returns an empty list.

    A production implementation should:
      1. Tokenize the description (language-aware — Arabic requires different
         tokenization than English).
      2. Match against a controlled skills taxonomy (to be defined in
         data/taxonomies/skills.json — not yet implemented).
      3. Apply NER or a fine-tuned classifier for skill span detection.
      4. Return normalized skill labels from the taxonomy, not raw text spans.

    Do not implement this as a bag-of-words over common tech terms — that
    produces noisy output that degrades matching quality.

    Parameters
    ----------
    title:
        Job title.
    description:
        Full job description text (plain text, not HTML).

    Returns
    -------
    list[str]
        Extracted skill labels. Empty list until implemented.
    """
    # TODO: implement taxonomy-based extraction.
    logger.debug("extract_skills() is a placeholder — returning empty list")
    return []


# ---------------------------------------------------------------------------
# Salary hint extraction
# ---------------------------------------------------------------------------

def extract_salary_hint(text: str) -> Optional[str]:
    """
    Extract salary information as stated in the posting text.

    Returns the raw matched string without normalization. Does not estimate,
    impute, or infer salary from role type or seniority.

    Parameters
    ----------
    text:
        Job description or any other text field that may contain salary info.

    Returns
    -------
    Optional[str]
        Raw salary string as found in the text, or None if not found.
    """
    match = _SALARY_PATTERN.search(text)
    if match:
        return match.group(0).strip()
    return None


# ---------------------------------------------------------------------------
# Saudization signal detection
# ---------------------------------------------------------------------------

def extract_saudization_signal(text: str) -> Optional[str]:
    """
    Detect explicit Saudi national preference or Saudization language in a posting.

    Returns the matched text fragment verbatim. Does not interpret or classify
    what it means for eligibility — that is the Saudi Intelligence Layer's job.

    Placeholder: pattern list is minimal and requires expansion against a
    corpus of real Saudi job postings.

    Parameters
    ----------
    text:
        Job description text.

    Returns
    -------
    Optional[str]
        The matched signal phrase, or None if not found.
    """
    _SAUDIZATION_PATTERNS = [
        re.compile(r"saudi national[s]?\s+(only|preferred|required)", re.I),
        re.compile(r"must be a saudi", re.I),
        re.compile(r"سعودي\s+(فقط|مفضل|مطلوب)", re.U),
        re.compile(r"للمواطن\w*\s+السعودي", re.U),
        re.compile(r"nitaqat", re.I),
        re.compile(r"saudization", re.I),
    ]
    for pattern in _SAUDIZATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return None


# ---------------------------------------------------------------------------
# Normalization pipeline
# ---------------------------------------------------------------------------

def enrich(posting: JobPosting) -> JobPosting:
    """
    Apply all extraction passes to a JobPosting and return an enriched copy.

    This is the primary entry point for the parsing layer. It takes a posting
    as produced by a connector's normalize() method and adds derived fields:
    language, seniority, employment_type, skills, salary_hint,
    and saudization_signal.

    Fields that are already populated on the input posting are not overwritten.
    The connector's normalize() has higher authority over directly structured
    source fields; this function fills in what could not be extracted structurally.

    Parameters
    ----------
    posting:
        A normalized JobPosting from a connector.

    Returns
    -------
    JobPosting
        A new JobPosting with extracted fields populated where possible.
        The input is not modified.
    """
    combined_text = f"{posting.title}\n{posting.description}"
    updates: dict = {}

    # Language detection
    if posting.language == Language.UNKNOWN:
        updates["language"] = detect_language(combined_text)

    # Seniority
    if posting.seniority is None:
        detected_seniority = extract_seniority(posting.title, posting.description)
        if detected_seniority is not None:
            updates["seniority"] = detected_seniority

    # Employment type
    if posting.employment_type is None:
        detected_type = extract_employment_type(posting.title, posting.description)
        if detected_type is not None:
            updates["employment_type"] = detected_type

    # Skills
    if not posting.skills:
        updates["skills"] = extract_skills(posting.title, posting.description)

    # Salary hint
    if posting.salary_hint is None:
        raw_salary = extract_salary_hint(posting.description)
        if raw_salary:
            from ingestion.models.job_posting import SalaryHint
            updates["salary_hint"] = SalaryHint(raw=raw_salary)

    # Saudization signal
    if posting.saudization_signal is None:
        signal = extract_saudization_signal(posting.description)
        if signal:
            updates["saudization_signal"] = signal

    if not updates:
        return posting

    return replace(posting, **updates)

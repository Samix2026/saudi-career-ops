"""
Job parsing pipeline — Saudi Career Ops.

Transforms a raw JobPosting (as produced by a connector's normalize()) into
a more fully analyzed record by extracting structured signals from free text.

Taxonomy-backed matching is used wherever a controlled vocabulary exists in
data/taxonomies/. Skills, employment types, and job titles are resolved to
normalized IDs from the taxonomy rather than raw text spans. Regex patterns
remain as fallback for fields not covered by the taxonomy files.

Design notes:
- TaxonomyMatcher is a module-level lazy singleton. Taxonomy files are loaded
  once on first use; subsequent calls hit in-memory indexes.
- Parsing functions are side-effect-free. They accept text and return values.
  enrich() assembles them into a JobPosting without mutating its input.
- If taxonomy files are missing or unreadable, matching falls back gracefully
  with a warning. The pipeline does not raise.
- Saudi-specific extraction logic beyond text parsing (Saudization scoring,
  PIF tagging, Nitaqat classification) belongs in saudi_intel.py (not yet
  implemented) — not here.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import Optional

from ingestion.models.job_posting import (
    EmploymentType,
    JobPosting,
    Language,
    SalaryHint,
    Seniority,
)

logger = logging.getLogger(__name__)

# Taxonomy files sit at data/taxonomies/ relative to the repository root.
# This file is at ingestion/parsers/job_parser.py, so we go up three levels.
_TAXONOMY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "taxonomies"


# ---------------------------------------------------------------------------
# Taxonomy loader
# ---------------------------------------------------------------------------

def _load_taxonomy(filename: str) -> Optional[dict]:
    """
    Load a taxonomy JSON file from the taxonomy directory.
    Returns None (with a warning) if the file is missing or unreadable.
    """
    path = _TAXONOMY_DIR / filename
    if not path.exists():
        logger.warning(
            "Taxonomy file not found: %s — related matching will be skipped. "
            "Run from the repository root or check data/taxonomies/.",
            path,
        )
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load taxonomy %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# TaxonomyMatcher
# ---------------------------------------------------------------------------

class TaxonomyMatcher:
    """
    Phrase-matching engine backed by the taxonomy JSON files.

    Builds four in-memory lookup indexes on initialization — one each for
    skills, job titles, employment types, and Saudi programs. Every canonical
    name, alias, and language variant from the taxonomy is an entry key.

    Matching is longest-match-first: phrases are sorted by length descending
    before scanning, so "Power BI Desktop" is checked before "Power BI", and
    "دوام كامل" is checked before "كامل". Matched spans are marked consumed
    to prevent a shorter sub-phrase from double-matching.

    Matching is Unicode-aware. Word boundaries use (?<!\\w) / (?!\\w) anchors
    which work correctly with Arabic script under Python's re.UNICODE semantics.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        root = data_dir or _TAXONOMY_DIR

        skills_data = _load_taxonomy("skills.json") if root == _TAXONOMY_DIR else _load_from(root, "skills.json")
        titles_data = _load_taxonomy("job-titles.json") if root == _TAXONOMY_DIR else _load_from(root, "job-titles.json")
        emp_data = _load_taxonomy("employment-types.json") if root == _TAXONOMY_DIR else _load_from(root, "employment-types.json")
        programs_data = _load_taxonomy("saudi-programs.json") if root == _TAXONOMY_DIR else _load_from(root, "saudi-programs.json")

        # phrase (lowercase) -> normalized id or EmploymentType
        self._skill_index: dict[str, str] = {}
        self._title_index: dict[str, tuple[str, str]] = {}  # -> (id, seniority_hint)
        self._employment_index: dict[str, EmploymentType] = {}
        self._program_index: dict[str, str] = {}

        if skills_data:
            self._build_skill_index(skills_data.get("skills", []))
        if titles_data:
            self._build_title_index(titles_data.get("job_titles", []))
        if emp_data:
            self._build_employment_index(emp_data.get("employment_types", []))
        if programs_data:
            self._build_program_index(programs_data.get("programs", []))

        # Pre-sort longest-first for greedy matching
        self._skill_phrases = sorted(self._skill_index, key=len, reverse=True)
        self._title_phrases = sorted(self._title_index, key=len, reverse=True)
        self._employment_phrases = sorted(self._employment_index, key=len, reverse=True)
        self._program_phrases = sorted(self._program_index, key=len, reverse=True)

        logger.debug(
            "TaxonomyMatcher loaded: %d skill phrases, %d title phrases, "
            "%d employment phrases, %d program phrases",
            len(self._skill_index),
            len(self._title_index),
            len(self._employment_index),
            len(self._program_index),
        )

    # ------------------------------------------------------------------
    # Index builders
    # ------------------------------------------------------------------

    def _build_skill_index(self, skills: list) -> None:
        for entry in skills:
            skill_id = entry.get("id")
            if not skill_id:
                continue
            phrases: list[str] = [entry.get("canonical_name", "")]
            phrases.extend(entry.get("aliases", []))
            phrases.extend(entry.get("language_variants", {}).values())
            for phrase in phrases:
                if phrase and phrase.strip():
                    self._skill_index[phrase.strip().lower()] = skill_id

    def _build_title_index(self, titles: list) -> None:
        for entry in titles:
            title_id = entry.get("id")
            seniority_hint = entry.get("seniority_hint", "")
            if not title_id:
                continue
            phrases: list[str] = [entry.get("canonical_name", "")]
            phrases.extend(entry.get("english_variants", []))
            phrases.extend(entry.get("arabic_variants", []))
            for phrase in phrases:
                if phrase and phrase.strip():
                    self._title_index[phrase.strip().lower()] = (title_id, seniority_hint)

    def _build_employment_index(self, emp_types: list) -> None:
        for entry in emp_types:
            model_value = entry.get("model_value")
            if not model_value:
                continue
            try:
                emp_type = EmploymentType(model_value)
            except ValueError:
                logger.warning("Unknown EmploymentType model_value %r in taxonomy — skipping", model_value)
                continue
            phrases: list[str] = [entry.get("canonical_name", "")]
            phrases.extend(entry.get("english_variants", []))
            phrases.extend(entry.get("arabic_variants", []))
            for phrase in phrases:
                if phrase and phrase.strip():
                    self._employment_index[phrase.strip().lower()] = emp_type

    def _build_program_index(self, programs: list) -> None:
        for entry in programs:
            program_id = entry.get("id")
            if not program_id:
                continue
            phrases: list[str] = [
                entry.get("canonical_name", ""),
                entry.get("arabic_name", ""),
            ]
            for phrase in phrases:
                if phrase and phrase.strip():
                    self._program_index[phrase.strip().lower()] = program_id

    # ------------------------------------------------------------------
    # Public matching API
    # ------------------------------------------------------------------

    def match_skills(self, text: str) -> list[str]:
        """
        Return skill IDs found in text.

        Results are deduplicated and ordered by position of first match.
        Longer phrases take priority: "Advanced Excel" matches before "Excel".
        """
        return self._match_phrases(text, self._skill_phrases, self._skill_index)

    def match_employment_type(self, text: str) -> Optional[EmploymentType]:
        """
        Return the EmploymentType matched in text, or None.

        Tamheer is checked before all other types because the Arabic and English
        terms for Tamheer ("تمهير", "trainee") overlap with internship vocabulary.
        Tamheer must not be classified as a generic internship.
        """
        text_lower = text.lower()

        # Priority check: Tamheer first
        for phrase in self._employment_phrases:
            if self._employment_index.get(phrase) == EmploymentType.TAMHEER:
                if self._phrase_in_text(phrase, text_lower):
                    return EmploymentType.TAMHEER

        # Then general matching
        for phrase in self._employment_phrases:
            if self._phrase_in_text(phrase, text_lower):
                return self._employment_index[phrase]

        return None

    def match_job_title(self, title: str) -> Optional[tuple[str, str]]:
        """
        Match a job title against the title taxonomy.

        Returns (title_id, seniority_hint) if a match is found, else None.
        Useful for deriving seniority from Arabic titles where regex patterns
        do not apply.
        """
        title_lower = title.lower()
        for phrase in self._title_phrases:
            if self._phrase_in_text(phrase, title_lower):
                return self._title_index[phrase]
        return None

    def match_saudi_programs(self, text: str) -> list[str]:
        """
        Return program IDs explicitly mentioned in text.

        Useful for flagging postings that reference Tamheer, Jadarat, HRDF,
        or other program names as content signals (distinct from employment
        type classification).
        """
        return self._match_phrases(text, self._program_phrases, self._program_index)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _phrase_in_text(phrase: str, text_lower: str) -> bool:
        """
        Return True if phrase appears in text_lower as a complete word unit.

        Uses zero-width word-boundary anchors ((?<!\\w) / (?!\\w)) rather than
        \\b so that the match works correctly with both Arabic and Latin script.

        Arabic conjunction prefix handling: Arabic conjunctions (و ف ب ل ك) are
        single letters that attach to the following word without a space, e.g.
        "وباور بي آي" for "and Power BI". A second pass allows a conjunction
        character at a word boundary before the phrase to still count as a match.

        Both phrase and text_lower must already be lowercased.
        """
        if not phrase:
            return False
        escaped = re.escape(phrase)
        if re.search(r"(?<!\w)" + escaped + r"(?!\w)", text_lower, re.UNICODE):
            return True
        # Arabic conjunction prefix: و ف ب ل ك (waw, fa, ba, lam, kaf)
        if any("؀" <= c <= "ۿ" for c in phrase):
            conj_pattern = r"(?:^|(?<=\s))[وفبلك]" + escaped + r"(?!\w)"
            if re.search(conj_pattern, text_lower, re.UNICODE):
                return True
        return False

    def _match_phrases(
        self,
        text: str,
        sorted_phrases: list[str],
        index: dict,
    ) -> list[str]:
        """
        Scan text for all phrases in sorted_phrases (longest-first).
        Returns deduplicated IDs in order of first match position.
        Consumed character spans are tracked to prevent sub-phrase double-matching.

        Two patterns are tried per phrase:
        1. Strict word boundary: (?<!\\w)PHRASE(?!\\w)
        2. Arabic conjunction prefix (و ف ب ل ك): for Arabic-script phrases,
           also try matching when a conjunction character precedes the phrase
           directly after a space (e.g. "وباور بي آي" → matches "باور بي آي").
        """
        text_lower = text.lower()
        matched_ids: list[str] = []
        seen_ids: set[str] = set()
        consumed: list[tuple[int, int]] = []

        for phrase in sorted_phrases:
            escaped = re.escape(phrase)
            candidates = [r"(?<!\w)" + escaped + r"(?!\w)"]
            # Arabic conjunction prefix fallback
            if any("؀" <= c <= "ۿ" for c in phrase):
                candidates.append(r"(?:^|(?<=\s))[وفبلك]" + escaped + r"(?!\w)")

            for pattern in candidates:
                for m in re.finditer(pattern, text_lower, re.UNICODE):
                    start, end = m.start(), m.end()
                    if any(cs <= start < ce or cs < end <= ce for cs, ce in consumed):
                        continue
                    item_id = index[phrase]
                    consumed.append((start, end))
                    if item_id not in seen_ids:
                        seen_ids.add(item_id)
                        matched_ids.append(item_id)

        return matched_ids


def _load_from(data_dir: Path, filename: str) -> Optional[dict]:
    """Load a taxonomy file from a specific directory (used in tests)."""
    path = data_dir / filename
    if not path.exists():
        logger.warning("Taxonomy file not found: %s", path)
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return None


# Module-level lazy singleton. Loaded on first use, not at import time.
_matcher: Optional[TaxonomyMatcher] = None


def get_matcher() -> TaxonomyMatcher:
    """Return the module-level TaxonomyMatcher, initializing it on first call."""
    global _matcher
    if _matcher is None:
        _matcher = TaxonomyMatcher()
    return _matcher


# ---------------------------------------------------------------------------
# Arabic character range (Unicode block: U+0600–U+06FF)
# ---------------------------------------------------------------------------
_ARABIC_CHAR_RE = re.compile(r"[؀-ۿ]")

# ---------------------------------------------------------------------------
# Seniority patterns (regex, applied to title/description text).
# Taxonomy title matching provides seniority hints for known titles;
# these regex patterns handle titles not in the taxonomy.
# Order is priority: more specific checks before less specific.
# ---------------------------------------------------------------------------
_SENIORITY_PATTERNS: list[tuple[re.Pattern, Seniority]] = [
    (re.compile(r"\bchief\b|\bcxo\b|\bceo\b|\bcto\b|\bcfo\b|\bcoo\b", re.I), Seniority.EXECUTIVE),
    (re.compile(r"\bvice president\b|\bvp\b", re.I), Seniority.EXECUTIVE),
    (re.compile(r"\bdirector\b|\bمدير عام\b|\bرئيس\b", re.I | re.U), Seniority.DIRECTOR),
    (re.compile(r"\bmanager\b|\bhead of\b|\bhead,\b|\bمدير\b", re.I | re.U), Seniority.MANAGER),
    (re.compile(r"\bprincipal\b|\bstaff\b|\blead\b|\bقائد\b", re.I | re.U), Seniority.LEAD),
    (re.compile(r"\bsenior\b|\bsr\.\b|\bأول\b|\bمتقدم\b", re.I | re.U), Seniority.SENIOR),
    (re.compile(r"\bmid.level\b|\bmiddle\b", re.I), Seniority.MID),
    (re.compile(r"\bjunior\b|\bjr\.\b|\bمبتدئ\b", re.I | re.U), Seniority.JUNIOR),
    (re.compile(r"\bintern\b|\btrainee\b|\btamheer\b|\bتمهير\b|\bمتدرب\b", re.I | re.U), Seniority.ENTRY),
]

# ---------------------------------------------------------------------------
# Salary hint pattern
# Matches both currency-first ("SAR 18,000–24,000") and number-first formats
# ("18,000–24,000 SAR"), as well as Arabic currency terms (ريال, ر.س).
# ---------------------------------------------------------------------------
_SALARY_PATTERN = re.compile(
    r"(?:"
    r"(?:SAR|USD|EUR|GBP)\s+[\d,،]+(?:\s*[-–]\s*[\d,،]+)?"   # currency-first
    r"|"
    r"[\d,،]+(?:\s*[-–]\s*[\d,،]+)?\s*(?:SAR|USD|EUR|GBP|ريال|ر\.س)"  # number-first
    r")",
    re.I | re.U,
)

# ---------------------------------------------------------------------------
# Saudization signal patterns
# ---------------------------------------------------------------------------
_SAUDIZATION_PATTERNS = [
    re.compile(r"saudi national[s]?\s+are\s+(encouraged|preferred|required)", re.I),
    re.compile(r"saudi national[s]?\s+(only|preferred|required|encouraged)", re.I),
    re.compile(r"must be (a )?saudi", re.I),
    re.compile(r"سعودي\s+(فقط|مفضل|مطلوب)", re.U),
    re.compile(r"للمواطن\w*\s+السعودي", re.U),
    re.compile(r"يُفضَّل.{0,20}المواطنين السعوديين", re.U),
    re.compile(r"nitaqat", re.I),
    re.compile(r"saudization", re.I),
]


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def detect_language(text: str) -> Language:
    """
    Detect whether text is Arabic, English, or mixed, based on script ratios.

    Counts Arabic Unicode characters (U+0600–U+06FF) as a fraction of all
    word characters. Thresholds: >=50% Arabic → ARABIC, >=15% → MIXED,
    else ENGLISH.

    This is a ratio heuristic, not a language model. It works well for
    Saudi job postings but has not been validated against a labeled corpus.
    A production upgrade would use a classifier (langdetect, fasttext, or
    CAMeL Tools) with calibrated thresholds.
    """
    if not text or not text.strip():
        return Language.UNKNOWN

    total_chars = len(re.findall(r"\w", text, re.U))
    if total_chars == 0:
        return Language.UNKNOWN

    arabic_chars = len(_ARABIC_CHAR_RE.findall(text))
    arabic_ratio = arabic_chars / total_chars

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
    Extract seniority level from a job title, with two strategies:

    1. Taxonomy lookup: match the title against known job titles in the taxonomy.
       If a match is found, the seniority_hint from the taxonomy is used.
       This covers Arabic titles that regex alone cannot handle.

    2. Regex fallback: apply seniority patterns to the title text. Used when
       the title is not in the taxonomy or the taxonomy lookup finds no match.

    If neither strategy produces a result, the description is scanned as a
    lower-confidence fallback.
    """
    # Strategy 1: taxonomy-backed title match
    matcher = get_matcher()
    title_match = matcher.match_job_title(title)
    if title_match:
        title_id, seniority_hint = title_match
        if seniority_hint:
            try:
                return Seniority(seniority_hint)
            except ValueError:
                logger.debug("Unrecognized seniority_hint %r for title_id %s", seniority_hint, title_id)

    # Strategy 2: regex patterns on title
    for pattern, level in _SENIORITY_PATTERNS:
        if pattern.search(title):
            return level

    # Fallback: regex on description (lower confidence)
    for pattern, level in _SENIORITY_PATTERNS:
        if description and pattern.search(description):
            logger.debug("Seniority %s inferred from description (not title) — lower confidence", level.value)
            return level

    return None


# ---------------------------------------------------------------------------
# Employment type extraction
# ---------------------------------------------------------------------------

def extract_employment_type(title: str, description: str = "") -> Optional[EmploymentType]:
    """
    Detect employment type from job text using the taxonomy alias index.

    The taxonomy covers both Arabic and English variants for each employment
    type. Tamheer is always checked first to prevent it being classified as a
    generic internship.

    Falls back to hardcoded regex patterns if the taxonomy is unavailable.
    """
    combined = f"{title}\n{description}"

    # Taxonomy-backed matching (preferred)
    matcher = get_matcher()
    if matcher._employment_phrases:
        return matcher.match_employment_type(combined)

    # Regex fallback (used only if taxonomy failed to load)
    _FALLBACK_PATTERNS: list[tuple[re.Pattern, EmploymentType]] = [
        (re.compile(r"\btamheer\b|\bتمهير\b", re.I | re.U), EmploymentType.TAMHEER),
        (re.compile(r"\binternship\b|\bمتدرب\b|\bتدريب\b", re.I | re.U), EmploymentType.INTERNSHIP),
        (re.compile(r"\bpart.time\b|\bدوام جزئي\b", re.I | re.U), EmploymentType.PART_TIME),
        (re.compile(r"\bcontract\b|\bfreelance\b|\bمستقل\b", re.I | re.U), EmploymentType.CONTRACT),
        (re.compile(r"\bfull.time\b|\bدوام كامل\b", re.I | re.U), EmploymentType.FULL_TIME),
    ]
    for pattern, emp_type in _FALLBACK_PATTERNS:
        if pattern.search(combined):
            return emp_type
    return None


# ---------------------------------------------------------------------------
# Skills extraction
# ---------------------------------------------------------------------------

def extract_skills(title: str, description: str) -> list[str]:
    """
    Extract skill IDs from job text using the taxonomy alias index.

    Returns canonical skill IDs (e.g. 'skill-sql', 'skill-python') rather than
    raw text spans. Every alias and language variant from skills.json is matched,
    including Arabic variants.

    Matching is longest-match-first and span-deduplicating — 'Advanced Excel'
    matches before 'Excel', and matching 'Power BI Desktop' prevents 'Power BI'
    and 'BI' from also matching the same span.

    Returns an empty list if the taxonomy failed to load (with a warning logged
    at load time). Does not estimate or guess skills from surrounding context.
    """
    combined = f"{title}\n{description}"
    matcher = get_matcher()
    skills = matcher.match_skills(combined)
    if not skills:
        logger.debug("extract_skills: no taxonomy matches in text (len=%d)", len(combined))
    return skills


# ---------------------------------------------------------------------------
# Salary hint extraction
# ---------------------------------------------------------------------------

def extract_salary_hint(text: str) -> Optional[str]:
    """
    Extract salary information exactly as stated in the posting text.

    Returns the raw matched string. Does not normalize, estimate, or infer
    salary from role type, seniority, or market benchmarks.

    Matches patterns of the form: <number or range> <currency code>.
    Supports SAR, USD, EUR, GBP, and Arabic currency terms (ريال, ر.س).
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
    Detect explicit Saudi national preference or Saudization language.

    Returns the matched phrase verbatim. Does not interpret eligibility
    implications — that is the Saudi Intelligence Layer's responsibility.

    Covers both Arabic and English formulations. The pattern list is minimal
    and should be expanded against a corpus of real Saudi job postings.
    """
    for pattern in _SAUDIZATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return None


# ---------------------------------------------------------------------------
# Saudi program detection
# ---------------------------------------------------------------------------

def extract_saudi_programs(text: str) -> list[str]:
    """
    Return program IDs explicitly mentioned in text (e.g. 'prog-tamheer',
    'prog-hrdf', 'prog-pif-ecosystem').

    This is a content signal — distinct from employment_type classification.
    A posting that mentions 'HRDF' in its description is flagged here even if
    the role is full-time, not a Tamheer placement.
    """
    matcher = get_matcher()
    return matcher.match_saudi_programs(text)


# ---------------------------------------------------------------------------
# Enrichment pipeline
# ---------------------------------------------------------------------------

def enrich(posting: JobPosting) -> JobPosting:
    """
    Apply all extraction passes to a JobPosting and return an enriched copy.

    This is the primary entry point for the parsing layer. It fills in fields
    that require text analysis: language, seniority, employment_type, skills,
    salary_hint, and saudization_signal.

    Fields already populated on the input posting are not overwritten — the
    connector's structured extraction takes authority over text heuristics.

    The input posting is not mutated. A new instance is returned via
    dataclasses.replace().
    """
    combined_text = f"{posting.title}\n{posting.description}"
    updates: dict = {}

    if posting.language == Language.UNKNOWN:
        updates["language"] = detect_language(combined_text)

    if posting.seniority is None:
        seniority = extract_seniority(posting.title, posting.description)
        if seniority is not None:
            updates["seniority"] = seniority

    if posting.employment_type is None:
        emp_type = extract_employment_type(posting.title, posting.description)
        if emp_type is not None:
            updates["employment_type"] = emp_type

    if not posting.skills:
        updates["skills"] = extract_skills(posting.title, posting.description)

    if posting.salary_hint is None:
        raw_salary = extract_salary_hint(posting.description)
        if raw_salary:
            updates["salary_hint"] = SalaryHint(raw=raw_salary)

    if posting.saudization_signal is None:
        signal = extract_saudization_signal(posting.description)
        if signal:
            updates["saudization_signal"] = signal

    if not updates:
        return posting
    return replace(posting, **updates)

# ingestion/

The ingestion layer collects raw job data from external sources, normalizes it
into a consistent internal structure, and passes it downstream for analysis.

---

## Philosophy

The ingestion layer's job is to get data in and get it clean. It does not analyze,
score, or make decisions. Every component in this layer should be replaceable
without affecting downstream logic.

Three principles govern every connector:

**Normalize, don't interpret.** A connector converts source-specific data into
a `JobPosting`. It does not guess at missing fields, infer seniority from salary,
or apply Saudi market context. That is the parsing and Saudi intelligence layers' job.

**Respect the source.** Every connector must comply with the source's terms of
service, rate limits, and authentication requirements. If a source does not permit
automated access, the connector is not built — it is documented as a future item
pending API access.

**Preserve the original.** The `raw` field on `JobPosting` retains the unmodified
source record. If parsing logic needs to change, records can be re-parsed from the
raw without re-fetching. Do not discard it.

---

## Legal Considerations

Each source has different legal constraints on automated access. These are not
uniform and must be assessed individually.

**LinkedIn** — Terms of service explicitly prohibit scraping. The public hiQ v. LinkedIn
ruling addressed CFAA liability for scraping public data but did not grant a general
right to do so, and LinkedIn continues to enforce its ToS. This connector requires
official API access. It is not implemented.

**Greenhouse / Lever / Ashby** — These platforms expose a public JSON feed specifically
for embedding job listings externally. This is intentional and the endpoints are
documented. Acceptable use still requires review of each platform's ToS; bulk crawling
of all companies on a platform is likely out of scope even if individual company
feeds are permitted.

**Saudi government platforms (Jadarat, Qiwa, Taqat)** — These are government-operated
systems. Automated access outside of any officially published API is not appropriate.
These connectors are planned pending official API documentation or data sharing
arrangements. They are not implemented.

**Bayt / GulfTalent** — Regional job boards with their own ToS. Review before
implementing. Public browsability of listings does not imply permission for
automated bulk extraction.

When in doubt: read the ToS, use the official API if one exists, and implement
conservatively on rate limits.

---

## Normalization Strategy

Raw records from different sources are structurally incompatible. A Greenhouse
posting looks nothing like a LinkedIn posting. The connector's `normalize()` method
is responsible for converting source-native structure into a `JobPosting`.

Fields that cannot be reliably derived from a source record are set to `None`,
not estimated. False precision in normalized data degrades matching quality.

After normalization, the `job_parser.enrich()` function applies extraction passes
to fill in fields that require text analysis: language detection, seniority
extraction, employment type detection, and saudization signal identification.

This separation means:
- Connector logic is deterministic and testable against known source records.
- Parsing logic can be improved without changing connectors.
- Each layer has a clear responsibility boundary.

---

## Taxonomy Matching

The parser uses `data/taxonomies/` as a controlled vocabulary for skills,
employment types, job titles, and Saudi programs. This replaces ad-hoc keyword
guessing with normalized IDs that are stable across the pipeline.

### How it works

`TaxonomyMatcher` loads four taxonomy files on first use and builds in-memory
lookup indexes keyed by lowercase phrase:

| Index | Source file | Returns |
|-------|-------------|---------|
| Skills | `skills.json` | `skill-*` IDs |
| Job titles | `job-titles.json` | `(title-* ID, seniority_hint)` |
| Employment types | `employment-types.json` | `EmploymentType` enum value |
| Saudi programs | `saudi-programs.json` | `prog-*` IDs |

Every `canonical_name`, `alias`, and `language_variants` entry from each taxonomy
file becomes a key in the relevant index. This means Arabic and English variants
are matched equally without a translation step.

### Matching strategy

Phrases are sorted longest-first before scanning. This means `"Power BI Desktop"`
is checked before `"Power BI"`, and `"Advanced Excel"` before `"Excel"`. Matched
character spans are marked consumed, preventing a shorter sub-phrase from claiming
the same text span.

**Arabic conjunction prefix handling:** Arabic conjunctions (و ف ب ل ك) attach to
the following word without a space — `"وباور بي آي"` means `"and Power BI"`. The
matcher applies a second-pass pattern that recognizes these prefixes, so an Arabic
skill that appears after a conjunction is still matched correctly.

### Tamheer priority

`match_employment_type()` always checks for Tamheer before any other employment
type. Arabic terms for on-the-job training (`متدرب`, `تدريب`) overlap with generic
internship vocabulary. Tamheer must be classified as `EmploymentType.TAMHEER`, not
`INTERNSHIP`, because they have different legal, compensation, and Nitaqat implications.

### Graceful degradation

If a taxonomy file is missing or unreadable, `TaxonomyMatcher` logs a warning and
skips that index. The remaining indexes still function. Existing regex-based
fallbacks remain active for employment type detection when the taxonomy is
unavailable.

### Returned values

Skills extraction returns taxonomy IDs (`skill-sql`, `skill-python`, etc.), not
raw text spans. These IDs are stable references that can be joined against the
taxonomy for display names, categories, or Arabic labels without re-parsing.

### Running the smoke tests

```bash
python scripts/smoke-test-parser.py           # pass/fail summary
python scripts/smoke-test-parser.py --verbose # all checks with detail
```

The smoke tests assert against known Arabic and English job texts and cover:
language detection, seniority extraction (English and Arabic titles), employment
type matching (including Tamheer), taxonomy-backed skills extraction in both
languages, salary hint detection (number-first and currency-first formats),
saudization signal detection, and Saudi program mention detection.

---

## Directory Structure

```
ingestion/
├── connectors/
│   ├── base.py          — Abstract base class, RateLimiter, error types
│   ├── linkedin.py      — LinkedIn Jobs (not implemented; ToS constraint)
│   ├── greenhouse.py    — Greenhouse public jobs API (not implemented)
│   └── lever.py         — Lever public postings API (not implemented)
├── models/
│   └── job_posting.py   — JobPosting dataclass and related enums
├── parsers/
│   └── job_parser.py    — Text extraction pipeline (language, seniority, skills)
├── output/
│   └── sample-output.json — Synthetic sample records for development/testing
└── README.md
```

---

## Future Saudi Integrations

The following sources are planned. None are currently implemented.

**Jadarat (jadarat.sa)** — HRDF's national talent platform. This is the most
important planned integration for Saudi national candidates. Access appears to
require authentication via the Absher/NafAz identity system. No public API is
documented. Will require either an official data sharing arrangement or a
published API before implementation proceeds.

**Qiwa Jobs (qiwa.sa)** — The Ministry of Human Resources labor platform. Job
postings here carry regulatory weight and are often Nitaqat-sensitive. Same
constraints as Jadarat — authentication required, no public API documented.

**Taqat (taqat.sa)** — HRDF's national employment portal. Postings are publicly
browsable, making this a more tractable integration than Jadarat or Qiwa. A
connector is planned once the browsable structure has been assessed for stability.

**Saudi Aramco / SABIC / STC direct portals** — Large employers with high-volume
posting activity. These use enterprise ATS platforms (Workday, Taleo) that are
complex to access programmatically. Integration planned after the simpler
connectors are operational.

---

## Adding a New Connector

1. Create a new file in `ingestion/connectors/` named after the source.
2. Subclass `BaseConnector` from `connectors/base.py`.
3. Implement `source_metadata()`, `fetch_jobs()`, `normalize()`, `validate()`.
4. Add the source to `data/saudi-job-sources.json` if not already present.
5. Add at least one synthetic sample record to `ingestion/output/sample-output.json`.
6. Document any ToS constraints in the connector's module docstring.

Connectors with `fetch_jobs()` raising `NotImplementedError` are acceptable as
structural placeholders. Do not ship a connector that makes network requests
without explicit operator configuration (credentials, rate limits, consent).

---

## Why No Active Scraping Yet

This version of the ingestion layer contains structure, not implementation.
The connectors are skeletons.

This is intentional:

1. **Legal review first.** Implementing a scraper before assessing the source's
   ToS is the wrong order of operations. The skeletons document the access model
   and legal constraints for each source before any requests are made.

2. **API access before scraping.** For sources with official APIs (LinkedIn,
   Greenhouse, Lever), the correct path is API access — not scraping a public
   web interface. Several of these require applications or partnerships.

3. **Architecture before data.** A clean, stable data model and pipeline
   architecture is more valuable than working scraping code built on a fragile
   foundation. The `JobPosting` model, connector interface, and parsing pipeline
   are the durable assets; the network calls are the easy part once those are right.

The connectors will be activated in order of access feasibility and Saudi market
relevance. Greenhouse and Lever are the most tractable (public JSON APIs, no auth
required, ToS review pending). Saudi government platforms are the highest value
and the most constrained.

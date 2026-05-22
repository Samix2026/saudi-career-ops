# candidate/

The candidate ingestion layer converts raw profile data into normalized
`CandidateProfile` objects ready for the matching engine. It handles manual
form submissions, API payloads, and structured dicts from future CV parsing
pipelines.

---

## Pipeline

```
raw dict
  → parser.parse_candidate()         RawCandidateInput
  → normalizer functions             typed + controlled-vocabulary values
  → profile_builder.build_profile()  CandidateProfile   (→ matching engine)
```

Each stage has a single responsibility. The parser handles structure; the
normalizer handles vocabulary; the builder handles inference and assembly.

---

## Philosophy

**Preserve before normalizing.** The original input dict is retained in
`RawCandidateInput.raw`. If normalization logic changes, profiles can be
re-normalized without re-collecting. Nothing in the raw input is discarded.

**Sparse data is valid.** A profile with only an id and a name is a valid
`RawCandidateInput`. It produces a `CandidateProfile` with `profile_completeness`
near 0.0 and `ConfidenceLevel.LOW` match results. Sparse profiles do not error
— they produce weaker matches with explicit data gaps.

**Inferred values are marked, not hidden.** When seniority is derived from
years-of-experience bands rather than a job title, a DEBUG log says so.
When program eligibility is hinted rather than explicitly stated, the hint
logic is documented in `profile_builder.py`. Consumers can audit the provenance
of every field.

**No fabrication.** The system does not estimate missing skill sets from
description text, infer seniority from compensation hints, or synthesize
experience from education records. What is absent from the input is absent
from the profile.

---

## Why Normalization Matters

Candidate skills and job skills must share the same ID space for the
matching engine to compare them. A job posting that requires `"Python"` and
a candidate who lists `"Python 3"` or `"python"` should match; without
normalization, they are three distinct strings.

`normalizer.normalize_skills()` resolves each raw skill label to a taxonomy ID
using the same `TaxonomyMatcher` instance that processes job postings. Both
sides of a match end up with `skill-python`, `skill-sql`, `skill-pmp`, etc.,
and the scorer's set-intersection logic works correctly.

Location normalization serves the same purpose for geographic comparison. The
scorer's location factor compares tokenized location strings; `"الرياض"` and
`"Riyadh"` must resolve to the same string before that comparison works.

---

## Arabic Input Support

The parser recognizes Arabic field keys in input dicts:

| Arabic key         | Canonical field        |
|--------------------|------------------------|
| `الاسم`            | `name`                 |
| `الاسم بالعربي`    | `name_arabic`          |
| `المهارات`         | `skills`               |
| `اللغات`           | `languages`            |
| `الجنسية`          | `nationality_status`   |
| `الخبرات`          | `experiences`          |
| `التعليم`          | `education`            |
| `الشهادات`         | `certifications`       |
| `الموقع المفضل`    | `preferred_locations`  |
| `مستعد للانتقال`   | `willing_to_relocate`  |

Language labels are normalized separately: `"العربية"`, `"عربي"`, `"ar"` all
map to `Language.ARABIC`; `"الإنجليزية"`, `"إنجليزي"`, `"en"` to
`Language.ENGLISH`.

---

## Data Integrity Principles

- No PII (names, national ID numbers, phone numbers, email addresses) is stored
  in repository files. Sample profiles in `data/sample-candidate-profiles.json`
  use synthetic data only.
- The `raw` field on `RawCandidateInput` retains the original input for
  auditing. It must not be logged at INFO or above in production.
- `CandidateProfileMetadata.raw_input_hash` contains a SHA-256 digest of the
  input dict. It is suitable for deduplication but is not a privacy-preserving
  identifier.

---

## Limitations of Inferred Data

**Years of experience from date ranges** is an approximation. Overlapping
concurrent roles are not detected and over-count. Undated roles are excluded
entirely and under-count. Use `years_experience_override` in the input to
supply an explicit value when the candidate states their total directly.

**Seniority from year bands** is a coarse last resort used when no job title
can be matched against the taxonomy or the seniority regex patterns. The bands
(`entry` < 1.5yr, `junior` < 3yr, `mid` < 5.5yr, etc.) are industry
approximations. A title-based match is always preferred.

**Saudi program eligibility hints** indicate what the data *suggests* —
not what is confirmed. Tamheer eligibility requires HRDF registration.
Co-op eligibility requires current enrollment and a cooperating institution.
HRDF subsidy eligibility requires conditions the profile does not capture.
All hints should be treated as prompts for verification, not authoritative claims.

---

## Directory Structure

```
candidate/
├── models.py           — RawCandidateInput and intermediate dataclasses
├── parser.py           — raw dict → RawCandidateInput
├── normalizer.py       — raw text → taxonomy IDs, enums, canonical strings
├── profile_builder.py  — RawCandidateInput → CandidateProfile
└── README.md
```

---

## Running the Smoke Tests

```bash
python scripts/smoke-test-candidate.py           # pass/fail summary
python scripts/smoke-test-candidate.py --verbose # per-check detail
```

Tests cover: bilingual field normalization, duplicate skill collapsing,
missing-field resilience, experience date inference, and Saudi program
eligibility hint detection.

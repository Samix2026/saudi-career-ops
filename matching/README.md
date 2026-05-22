# matching/

The matching layer compares a `CandidateProfile` against a `JobPosting` and
produces a `MatchResult`: a 0–100 score, an overall confidence level, and a
structured explanation of every factor that contributed to the score.

---

## Philosophy

**Scores are derived, not inferred.** Every point in the total score can be
traced to a specific piece of data — a skill that matched, a seniority band
gap, an employment type conflict. There are no hidden adjustments, no smoothing
factors, and no trained weights. A person reading the explanation can reconstruct
the score from the candidate profile and job posting alone.

**Explainability is not a feature — it is the design constraint.** A black-box
rank would be faster to build and easier to tune on aggregate metrics. It would
also be useless in a professional context where candidates and employers need to
understand *why* a match was or was not made. Every scoring function returns a
`detail` string that states exactly what was compared and what was found.

**Sparse data produces low confidence, not false precision.** When the candidate
profile is missing seniority, languages, or location preferences, the affected
components score conservatively and the overall confidence drops to LOW. This is
visible in the output and surfaces the data gaps explicitly.

---

## Scoring Factors

Six factors contribute to the total score. Weights are configurable via
`ScoringWeights`; the defaults reflect a general Saudi market match.

| Factor                 | Default weight | What it measures |
|------------------------|---------------|------------------|
| `skill_overlap`        | 0.35          | Fraction of job-required skills the candidate holds |
| `seniority_alignment`  | 0.20          | Band distance between candidate and role seniority |
| `employment_type`      | 0.15          | Candidate employment preference vs. job type |
| `language`             | 0.15          | Working language compatibility |
| `location`             | 0.10          | Geographic alignment, accounting for relocation willingness |
| `saudi_program`        | 0.05          | Tamheer eligibility and Saudization signal alignment |

The total score is `sum(component.score * component.weight) * 100`.

### Skill overlap

Candidate skills and job requirements are normalized before comparison: both
sides are lowercased, the `skill-` taxonomy prefix is stripped, and hyphens
are replaced with spaces. This means `skill-power-bi` and `"Power BI"` compare
as equal.

The score is recall-oriented: how many of the job's listed requirements does
the candidate cover? If the job lists no skills, the score is 0.5 with LOW
confidence rather than a false 100%.

### Seniority alignment

Seniority levels are mapped to a numeric rank (ENTRY=0 … EXECUTIVE=7). The
score degrades by 0.4 per band of distance: exact match = 1.0, one band off =
0.6, two bands = 0.2, three or more = 0.0. A gap of three or more bands also
triggers a red flag.

### Saudi program alignment

This factor is Saudi-specific. Two conditions are checked:

- **Tamheer role**: If the job is `EmploymentType.TAMHEER`, an expatriate
  candidate receives 0.0 and a red flag. A confirmed Tamheer-registered
  candidate receives 1.0. Saudi nationals without confirmed registration
  receive 0.7 with MEDIUM confidence.

- **Saudization signal**: If `job.saudization_signal` is populated, scores
  vary by nationality: Saudi national = 1.0, GCC national = 0.7, expatriate =
  0.2. Expatriates with a Saudization-signaling role also receive a Saudi
  observation note clarifying that a preference signal is not a hard legal bar
  (it depends on the employer's Nitaqat band).

---

## Red Flags vs. Concerns

**Red flags** are conditions that significantly reduce match viability and are
unlikely to be bridged by context. They appear in `explanation.red_flags`:

- Tamheer role + expatriate candidate
- "Saudi nationals only" hard requirement + expatriate candidate
- Seniority gap ≥ 3 bands

**Concerns** are softer signals that warrant attention but are not disqualifying:

- Location mismatch without relocation willingness
- Working language mismatch
- Tamheer role with candidate experience > 2 years
- Employment type preference mismatch
- Seniority gap of 1–2 bands

---

## Limitations

This is a rule-based system. These limitations are inherent to that design:

- **No semantic skill matching.** `"data analysis"` and `"data analytics"` do not
  match unless they normalize to the same string. Use taxonomy IDs on both sides
  for best results — run candidates through the same `TaxonomyMatcher` used by
  the job parser.

- **No experience weighting within a seniority band.** Two candidates both
  labeled SENIOR score identically on seniority regardless of their years of
  experience.

- **Location matching is token-based.** `"Riyadh"` matches `"Riyadh, Saudi Arabia"`
  and `"Riyadh Financial District"`, but `"الرياض"` (Arabic) does not match
  `"Riyadh"` unless both are run through a normalizer first.

- **Salary is not scored.** Compensation information in job postings is too
  inconsistently structured across sources to compare reliably. It appears in
  `JobPosting.salary_hint` for display but is not a scoring factor.

---

## Directory Structure

```
matching/
├── models.py        — CandidateProfile, MatchResult, MatchExplanation, enums
├── scorer.py        — Scorer class and per-factor scoring functions
├── explanations.py  — build_explanation(): narrative assembly from components
└── README.md
```

---

## Running the Smoke Tests

```bash
python scripts/smoke-test-matching.py           # pass/fail summary
python scripts/smoke-test-matching.py --verbose # full score breakdown per scenario
```

The smoke tests cover four scenarios:

1. **Strong match** — Saudi national data analyst vs. Riyadh data analyst role
2. **Weak match** — Expatriate with mismatched skills and location
3. **Tamheer mismatch** — Experienced candidate vs. Tamheer entry-level role
4. **Bilingual mismatch** — English-only candidate vs. Arabic-language role

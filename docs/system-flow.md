# System Flow — Saudi Career Ops

This document describes how Saudi Career Ops processes information from raw job data
through to structured career intelligence. Each layer is described in terms of its
inputs, outputs, responsibilities, and current implementation status.

The system is designed as a pipeline of discrete analytical layers. Layers are loosely
coupled: each produces a structured artifact that the next layer consumes. This makes
individual layers testable and replaceable without redesigning the whole system.

---

## Overview

```
Job Sources
    │
    ▼
[1] Job Ingestion Layer        — Collects and normalizes raw job postings
    │
    ▼
[2] Parsing Layer              — Extracts structured data from unstructured text
    │
    ▼
[3] Candidate Analysis Layer   — Parses and interprets the candidate's profile
    │
    ▼
[4] Saudi Intelligence Layer   — Applies Saudi market context to both sides
    │
    ▼
[5] Matching Engine            — Produces scored, explainable job-candidate matches
    │
    ▼
[6] Reality-Check Layer        — Surfaces honest constraints and market signals
    │
    ▼
[7] Tracking Layer             — Manages the active application pipeline
```

Each layer is described below.

---

## Layer 1 — Job Ingestion

**Purpose:** Collect job postings from external sources and normalize them into a
consistent internal format for downstream processing.

**Responsibility boundary:** This layer handles acquisition and structural normalization
only. It does not interpret, score, or analyze content — that belongs to Layer 2.

### Sources (Current)

**LinkedIn** — The dominant discovery surface for Saudi professional roles. Postings
vary significantly in quality: some are detailed, many are thin. Language mix is
unpredictable — a single posting may switch between Arabic and English mid-sentence.

**Lever / Greenhouse / Ashby** — ATS platforms used by multinational companies and
regional HQ entities. Postings from these systems tend to be structured and
English-primary. They often include more detail on requirements and process than
direct company postings.

**Saudi company career portals** — Direct career pages from Saudi employers. These
are highly heterogeneous in structure, language, and update frequency. Arabic-primary
postings are more common here than on LinkedIn. Many of the largest Saudi employers
(Saudi Aramco, STC, SABIC, government-linked entities) maintain substantial direct
portals.

### Sources (Future)

**Jadarat** — The HRDF-operated national talent platform. Jadarat is the official
channel for many government-adjacent and Vision 2030-linked roles. Integration would
require respecting Jadarat's terms of access; any future implementation must be
read-only and rate-limited.

**Qiwa Jobs** — The job posting function within Qiwa is an emerging channel, particularly
for roles subject to Nitaqat requirements. Access to this data is subject to regulatory
constraints that have not been assessed at the time of writing.

### Output

A normalized job record containing:
- Source identifier and retrieval timestamp
- Raw text (Arabic and/or English, preserved as-is)
- Detected language(s)
- Posting URL and employer identifier
- Metadata: location, posted date, ATS platform if identifiable

The normalized record is passed to the Parsing Layer without modification to content.

---

## Layer 2 — Parsing

**Purpose:** Extract structured data from the normalized job record. Transform
unstructured text into a schema that downstream layers can reason over.

**Responsibility boundary:** This layer extracts and structures. It does not evaluate
fit or apply Saudi market context — that belongs to Layers 4 and 5.

### Arabic Job Descriptions

Arabic-language content requires language-aware extraction. Key considerations:

- Role titles in Arabic do not always map cleanly to English equivalents. Preserve
  the original Arabic title as the canonical identifier; include an English rendering
  only as a secondary field.
- Requirements expressed in Arabic may carry cultural or regulatory specificity
  that is lost in translation (e.g., terms that imply Saudi national preference,
  references to specific certifications only recognized within Saudi Arabia).
- Mixed-language postings (Arabic body, English requirements table, or vice versa)
  must be handled as a single document, not split.

### English Job Descriptions

English-language extraction is more tractable but not without ambiguity. Common issues:
vague seniority language ("senior" means different things across companies and sectors),
requirements that bundle must-haves with nice-to-haves without clear separation, and
salary fields that are either absent or expressed as ranges with significant variance.

### Skills Extraction

Skills are extracted as a list with a distinction between:
- **Required** — explicitly stated as mandatory
- **Preferred** — stated as desirable but not disqualifying
- **Inferred** — not stated but strongly implied by role context

The inferred category must be flagged as inferred. It exists to surface implicit
requirements that a candidate should be aware of, not to fabricate requirements
the employer did not state.

### Salary Hints

Salary data in Saudi job postings is frequently absent, obfuscated ("competitive"),
or expressed as a range. When present, extract it. When absent, note the absence.
Do not estimate or impute salary ranges — this introduces false precision into
downstream matching.

### Experience Requirements

Extract stated years of experience and seniority indicators separately. A posting
that states "7+ years" and another that states "senior level" are expressing
related but distinct requirements. Both should be preserved, not collapsed.

### Sponsorship and Relocation Detection

Flag whether a posting indicates:
- Saudi national preference or requirement (explicit or inferred from Nitaqat context)
- Willingness to sponsor work authorization for expatriate candidates
- Relocation support offered or expected
- Tamheer or trainee classifications

These signals are input to the Saudi Intelligence Layer.

### Output

A structured job object with clearly labeled required/preferred/inferred fields,
language annotations, and flags for Saudi-specific signals. Confidence levels should
be attached to inferred fields.

---

## Layer 3 — Candidate Analysis

**Purpose:** Parse and interpret the candidate's profile to produce a structured
representation of their professional history, skills, and positioning.

**Responsibility boundary:** This layer reads the CV and builds a structured candidate
model. It does not evaluate the candidate against any specific role — that is the
Matching Engine's job.

### CV Parsing

Input is the candidate's CV in whatever form they provide: PDF, plain text, or
structured data. The output is a normalized profile with discrete fields.

Parsing challenges specific to Saudi candidates:
- CVs may include fields that are uncommon in Western formats: nationality, date
  of birth, Iqama number, marital status. These are conventional in Saudi hiring
  contexts. Extract them as metadata but do not treat them as analytical inputs
  beyond what the candidate has indicated is relevant.
- Arabic-language CVs should be parsed in Arabic-first mode. The candidate's own
  framing of their experience is the authoritative source.
- GOSI history, Tamheer placements, and national service periods are legitimate
  career timeline entries. Do not treat them as gaps.

### Career Timeline Analysis

Reconstruct a chronological employment timeline from the CV. Flag:
- Unexplained gaps (periods not covered by any stated role, education, or program)
- Overlapping roles (potentially contract, part-time, or advisory positions — clarify
  rather than flag as inconsistency)
- Progression patterns: lateral moves, promotions, sector changes, geographic shifts

The timeline is a factual reconstruction. Interpretation of what the timeline means
for a specific role is the Matching Engine's job.

### Skill Mapping

Map the candidate's stated and demonstrated skills against a normalized taxonomy.
Distinguish between:
- **Stated skills** — explicitly listed by the candidate
- **Demonstrated skills** — evidenced by role descriptions and accomplishments
- **Decayed skills** — stated or demonstrated but associated with roles more than
  several years in the past, with no recent evidence of continued use

Decayed skills should be preserved in the model but flagged. A skill last used seven
years ago is not the same as a current skill, and the matching engine should treat them
differently.

### Gap Analysis

Compare the candidate's skill and experience profile against the normalized taxonomy
to identify structural gaps: categories of skill or experience that are absent or
underdeveloped relative to their seniority level or stated target roles.

Gap analysis at this layer is role-agnostic. Role-specific gap analysis happens in
the Matching Engine.

### Seniority Estimation

Estimate the candidate's current seniority band from the totality of their profile:
years of experience, scope of responsibility, team size managed, budget ownership,
and organizational level of roles held. This estimate is used as a prior in matching
and in the Reality-Check Layer.

Seniority estimation should be expressed as a band (e.g., mid-level, senior, lead,
director) with a confidence level, not as a single authoritative label.

### Output

A structured candidate object: timeline, skill map with recency and confidence
annotations, seniority estimate, and extracted metadata. This object is the primary
input to the Matching Engine.

---

## Layer 4 — Saudi Intelligence

**Purpose:** Enrich both the parsed job object and the candidate model with Saudi
market context that generic systems do not carry. This layer does not score or match —
it attaches signals and classifications that make downstream analysis Saudi-aware.

**Responsibility boundary:** Context enrichment only. Outputs are annotations and
flags, not scores.

### Saudization Relevance

Classify the job posting's likely Nitaqat sensitivity:
- Is the employer likely subject to Nitaqat quotas (private sector, registered entity)?
- Does the role appear to be in a protected category?
- Does the posting include signals of Saudi national preference beyond legal requirement?

This classification informs the Matching Engine about whether expatriate candidates
face a structural barrier, separate from their qualifications.

Similarly, annotate the candidate's profile with their nationality status and any
relevant work authorization context.

### Tamheer Eligibility

If the candidate is a Saudi national recent graduate or early-career professional,
assess whether they meet the basic eligibility criteria for Tamheer placements.
Flag roles that may be offering Tamheer-track positions rather than direct employment,
as compensation and contract structure differ significantly.

### Government Ecosystem Understanding

Classify the employer's relationship to the government:
- Fully private
- Partially government-owned or affiliated
- Semi-government (e.g., Saudi Aramco, SABIC, STC before full privatization)
- PIF portfolio entity
- Government ministry or agency
- Vision 2030 program or megaproject entity

Hiring practices, compensation norms, job security, and career trajectory differ
substantially across these categories. The classification should be attached as
metadata, not collapsed into a single "public/private" binary.

### PIF Ecosystem Tagging

Flag roles associated with PIF entities and sub-entities. Known examples at the time
of writing: Neom, Diriyah Gate Development Authority, Red Sea Global, Qiddiya,
Saudi Entertainment Ventures, Lucid Motors (PIF investment), Saudi Vision 2030
delivery entities. This list evolves; the classification logic must be maintainable.

PIF-tagged roles carry specific implications: they often offer premium compensation,
involve large-scale projects with long timelines, and may carry implicit nationality
preferences even where not legally required.

### Regional HQ Relevance

Flag roles associated with the Regional Headquarters program. These roles are
predominantly in Riyadh, English-primary, and tied to multinationals establishing
regional presence. Compensation and seniority expectations are calibrated differently
from equivalent roles in Dubai or Bahrain — a senior role in a regional HQ may
command different terms than the same title in a regional hub outside Saudi Arabia.

### Hiring Patterns

Attach known hiring pattern signals where available:
- Typical time-to-hire for this employer or sector
- Known preferences for certain educational institutions or nationalities
- Seasonal hiring patterns (government budget cycles, Vision 2030 project phases)
- Whether the company has a pattern of posting roles that are not actually open

These signals are observational and should be flagged as approximate. They are
directional, not deterministic.

### Output

Annotated versions of the job object and candidate model, each carrying Saudi context
flags and classifications. These are consumed directly by the Matching Engine and the
Reality-Check Layer.

---

## Layer 5 — Matching Engine

**Purpose:** Produce a scored, explainable assessment of fit between a candidate
and a job. The score is an input to human judgment, not a replacement for it.

**Responsibility boundary:** Scoring and explanation. The engine does not decide
whether the candidate should apply.

### Explainable Scoring

The match score must be decomposed. A single number is not useful output.
The score should break down across at least:
- Skills alignment (required vs. candidate's demonstrated skills)
- Experience alignment (years, seniority band, domain)
- Saudi context alignment (Saudization, language, location)
- Role-level fit (is the candidate applying up, lateral, or down?)

Each component score should carry a brief explanation of what drove it.

### Match Confidence

Separate from the score: how confident is the engine in the score it produced?
Low confidence arises when the job posting is thin, the CV is ambiguous, or the
required skills are stated at a level of abstraction that makes assessment unreliable.
Low-confidence scores should be surfaced as such rather than presented as if they
were well-grounded.

### Red Flags

Explicit flags for conditions that significantly reduce match viability:
- Saudization barrier for expatriate candidate
- Hard requirement the candidate clearly does not meet
- Seniority mismatch beyond a reasonable range
- Language requirement not evidenced by candidate profile

Red flags are binary conditions, not score reductions. They should be stated plainly.

### Missing Requirements

A structured list of what the candidate lacks relative to the job's stated requirements.
Separated into:
- **Hard gaps** — required skills or experience the candidate does not have
- **Soft gaps** — preferred skills the candidate is missing
- **Saudi-specific gaps** — context gaps specific to Saudi market requirements
  (e.g., Arabic language proficiency not evidenced, no prior Saudi market experience)

### Market Competitiveness

An assessment of how the candidate is likely to rank relative to the probable
applicant pool for this specific role. This requires reasoning about:
- Typical candidate profile for this role type in Saudi Arabia
- Supply and demand signals for this skill set in this market
- Whether the employer's requirements suggest a thin or broad applicant pool

This assessment is directional and approximate. It should be presented with that
caveat attached.

### Output

A match record: component scores, confidence level, red flags, missing requirements,
and market competitiveness assessment. All fields include reasoning, not just values.

---

## Layer 6 — Reality-Check

**Purpose:** Produce an honest, direct assessment of constraints and risks that the
candidate may be underweighting. This layer exists specifically to say things that
are useful but uncomfortable.

**Responsibility boundary:** Honest signal generation. Not career counseling. Not
motivation. Not softened feedback.

### Honest Assessment

The reality check synthesizes the match record and Saudi context to produce a plain
statement of the candidate's position relative to this role. It addresses:
- Is the application realistic given the gap analysis?
- Are there structural barriers (Saudization, language, location) that make this
  role inaccessible regardless of qualifications?
- Is the candidate's self-positioning consistent with their actual profile?

### Overqualification Detection

Flag cases where the candidate's profile substantially exceeds the role's requirements.
Overqualification is a real phenomenon in Saudi hiring — employers frequently screen
out candidates they believe will leave quickly or be dissatisfied with the role's
scope. Where overqualification is detected, surface it explicitly.

### Weak CV Signals

Identify patterns in the CV that weaken the candidate's presentation:
- Vague role descriptions with no accomplishments
- Skills listed without evidence of use
- Employment history that is difficult to verify or reconstruct
- Formatting or structural issues that suggest lack of professional exposure

These are presented as fixable issues, not character assessments.

### Market Saturation

Flag where the candidate's skills or role target places them in an oversupplied
segment of the Saudi market. This is particularly relevant for:
- Entry-level roles in high-demand sectors that attract large applicant volumes
- Roles where Vision 2030 initiatives have created supply without equivalent demand
- Expatriate candidates competing in categories with strong Saudi national supply

### Language Limitations

If the candidate's CV is English-only and the target role or employer is Arabic-primary,
flag this explicitly. Language is a genuine filter in Saudi hiring, not a minor
formatting preference. Similarly, flag where Arabic language proficiency is expected
but not evidenced in the candidate's profile.

### Output

A structured reality-check report: honest assessment, overqualification flag, weak
signals list, market saturation flag, language limitations flag. Tone is direct.
No softening language.

---

## Layer 7 — Tracking

**Purpose:** Maintain a structured record of the candidate's active application pipeline
and support informed follow-up decisions.

**Responsibility boundary:** State management and signal organization. This layer does
not submit applications, send messages, or take actions on behalf of the candidate.

### Application Tracking

Record for each active application:
- Role and employer
- Source and application date
- Current stage (identified, applied, screening, interview, offer, closed)
- Last known status and date of last update
- Notes and context from the candidate

The tracking record is local and operator-managed. There is no automated status
polling from external systems.

### Interview Stages

Track the candidate's progression through a hiring process:
- Stage name and date
- Format (screening call, technical interview, panel, case study, etc.)
- Interviewer organization level where known
- Candidate's assessment of how the stage went
- Pending actions

This record exists to prevent the candidate from losing context across a multi-week
hiring process and to support preparation for subsequent stages.

### Rejection Analysis

When an application closes without an offer, record what is known about the outcome:
- Stage at which the application ended
- Reason given (if any)
- Inferred reason (if none given, what the pattern suggests)
- Whether the role was re-posted after rejection

Over time, rejection patterns surface signals: consistent rejection at a specific stage
indicates a different problem than consistent failure to get past initial screening.

### Follow-Up Suggestions

Generate structured suggestions for next actions on active applications:
- When to follow up on pending applications
- What to prepare for upcoming interview stages
- Whether an application has likely gone cold

Suggestions are generated based on elapsed time, stage, and employer pattern context.
They are presented as suggestions, not instructions.

### Output

A pipeline state object per candidate: all active applications with their current
state, pending actions, and timeline. Updated by the operator as events occur.

---

## Future Architecture

The current system operates as a prompt-driven pipeline. The following architectural
directions are under consideration for future development. None are implemented.

### Autonomous Agents

Agent-based orchestration would allow layers to be called conditionally and
iteratively rather than in a fixed sequence. For example: a matching agent that
calls the Saudi Intelligence layer only when signals from the parsing layer indicate
a Saudi-specific dimension requires assessment. This reduces unnecessary processing
and makes the pipeline adaptive.

Agents introduce coordination complexity and make behavior harder to trace. Any
agent-based architecture must preserve the traceability properties of the current
pipeline.

### Semantic Search

A search layer over the job corpus and candidate history using dense vector
representations would allow fuzzy matching on concepts rather than keywords:
finding roles related to a candidate's background without requiring exact skill
label overlap. Particularly relevant for Arabic content where terminology varies
significantly across employers.

### Embeddings and Vector Search

Embedding-based retrieval would index job postings and candidate profiles as
vectors, enabling similarity search at scale. This becomes relevant when the job
corpus grows beyond the point where prompt-based comparison of individual pairs
is practical.

Vector search surfaces candidates to roles and roles to candidates based on
representational similarity. It requires a maintained index and introduces
dependency on an embedding model. The tradeoffs — latency, cost, index staleness —
need to be evaluated against the scale at which they become relevant.

### Dashboards and Analytics

A structured view over the tracking layer and historical match data would allow
the operator to observe patterns over time: which sectors are generating matches,
which skill gaps recur, how long applications take at each stage. This is a
read-only view over data the system already produces; it does not require new
analytical capability.

### Market Analytics

Aggregate analysis over job postings and match data to surface market-level signals:
demand trends by skill, seniority distribution across sectors, salary range evolution,
hiring velocity by employer. This is directional intelligence for career planning,
not operational data for individual applications. It requires a sustained data
collection operation and carries data management obligations.

---

## Design Constraints

The following constraints apply across all layers and must be preserved in future
architecture decisions:

**No automated submission.** The system surfaces analysis. A human submits applications.
This boundary is fixed.

**No PII persistence.** Candidate data does not leave the local environment unless
the operator explicitly configures otherwise. The system does not log candidate
profiles to external services.

**Explainability over accuracy.** A lower-confidence result with clear reasoning
is preferred over a high-confidence result with opaque derivation. When the system
cannot explain why it produced an output, that is a design problem, not a tuning
problem.

**Saudi context is not optional.** The Saudi Intelligence Layer is not a feature that
can be disabled for a "generic" mode. This system is Saudi-first by design. Removing
that context would produce a materially worse system, not a more general one.

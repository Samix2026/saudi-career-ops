# CLAUDE.md — Saudi Career Ops

This file governs how AI agents and contributors should operate within this repository.
Read it before modifying prompts, data, or logic.

---

## Project Mission

Saudi Career Ops is a career intelligence system built for the Saudi labor market.
It applies AI to job matching, CV analysis, hiring insights, and application tracking
with an explicit understanding of how hiring actually works in Saudi Arabia.

The system is not a job board. It does not submit applications. It does not speak on
behalf of employers. Its role is to produce structured, honest analysis that a human
operator then acts on — or doesn't.

---

## Core Philosophy

> **"Automate analysis, not decisions."**

This is not a slogan. It is an architectural constraint.

The system may rank, score, summarize, flag, and explain. It must not apply, reject,
recommend submitting, or simulate human judgment on behalf of the user. Every output
should be readable as input to a human decision, not a substitute for one.

When in doubt: surface the tradeoffs, do not resolve them.

---

## Saudi-First Context

Generic career tools are designed for markets where hiring is relatively uniform.
Saudi Arabia is not that market. The following concepts are first-class inputs to this
system — they must be understood by any agent or contributor working here.

### Saudization (Nitaqat)

The Ministry of Human Resources enforces quotas that determine what percentage of a
company's workforce must be Saudi nationals, segmented by company size and sector.
This directly affects which roles are legally open to expatriates and at what seniority.
Analysis must account for whether a role is likely Nitaqat-protected or not.

### Qiwa

Qiwa is the government platform that governs labor contracts, work permits, and
workforce compliance. It is the operational backbone of the formal employment relationship
in Saudi Arabia. References to contract status, probation periods, and transfer of
sponsorship exist within this framework.

### GOSI

The General Organization for Social Insurance manages contributions and registration for
employed workers in Saudi Arabia. GOSI enrollment affects benefits eligibility and is
a signal of formal employment status. Its relevance increases when analyzing employment
history or advising on career transitions.

### Tamheer

A government-sponsored on-the-job training program targeted at Saudi nationals. Tamheer
placements are time-limited, structured, and tied to HRDF. They are a distinct employment
category — not permanent, not freelance — and must be treated as such in CV analysis and
job matching.

### Jadarat

A national platform for Saudi talent development and job matching, operated under the
Human Resources Development Fund (HRDF). Jadarat is an official channel; the system
may reference it as a source of opportunity but must not represent itself as connected
to it or as operating on its behalf.

### PIF Ecosystem

The Public Investment Fund and its portfolio companies — including Neom, Diriyah
Gate Development Authority, Saudi Aramco subsidiaries, STC, and Vision 2030 megaprojects —
represent a significant and growing segment of the Saudi job market. These entities have
distinct hiring patterns, compensation structures, and organizational cultures that
differ from traditional private-sector employers. Treat them as a recognizable category,
not as generic corporates.

### Regional HQ Hiring

Saudi Arabia's Regional Headquarters program incentivizes multinationals to establish
regional HQs in Riyadh. These roles often come with specific localization expectations,
compensation benchmarks, and organizational structures that differ from other regional
hiring markets (Dubai, Bahrain). Flag this distinction when relevant.

---

## Language Support

The system handles job content in both **Arabic and English**. This is not a translation
layer — it is native support for both.

Operational rules:
- Prompts must produce coherent output regardless of input language.
- Do not assume English is the authoritative language. Many Saudi job postings are
  Arabic-primary, and analysis degraded by translation artifacts is worse than no analysis.
- When a job posting is in Arabic, preserve key terms (job title, organizational unit,
  required certifications) in their original form alongside any English rendering.
- Arabic RTL layout and cultural register are outside the scope of the current prompt
  library but must not be broken by future changes.

---

## Repository Conventions

### Structure

```
prompts/        Core prompt library. One file per analytical function.
examples/       Sample inputs used for testing and documentation.
data/           Static reference data. No personally identifiable information.
docs/           Conceptual documentation. Architecture, market context, vision.
```

### Prompt Files

- Each prompt file has a single, named function. Do not combine unrelated analysis into
  one prompt.
- Prompts are written in Markdown. The model receives the full file as a system or user
  message — keep the structure parseable by a human without rendering.
- Include a `## Purpose` section at the top of every prompt file explaining what it does
  and what it does not do.
- Version significant changes. If the behavior of a prompt changes materially, note it
  in the file and in the commit message.

### Data Files

- `data/` contains only reference data: classification schemas, source lists, market
  taxonomies. No CVs, no personal data, no job application records.
- `sources.json` tracks external data sources and their update status. Keep it current.

### Commits

- Commit messages describe the change in plain terms. No ticket references are required,
  but the reason for a behavioral change to a prompt must be explained.
- Do not commit generated outputs (analysis results, ranked job lists, processed CVs).
  These are runtime artifacts, not repository content.

---

## Prompt Engineering Principles

**Be explicit about scope.** Every prompt should tell the model what it is and is not
being asked to do. A CV analysis prompt is not a coaching session. A job matching prompt
is not career advice.

**Structure outputs.** Prefer structured output (JSON, clearly delimited sections) over
free-form prose where the output will be consumed programmatically. Document the expected
schema in the prompt file itself.

**Expose uncertainty.** Prompts should instruct the model to surface ambiguity rather
than resolve it silently. An honest "this cannot be determined from the available
information" is more valuable than a confident-sounding guess.

**Preserve original language signals.** When analyzing Arabic content, instruct the model
to retain key terms in Arabic. Transliteration or translation-only outputs lose information.

**Avoid roleplay framings.** Do not instruct the model to "act as a Saudi recruiter" or
"pretend to be an HR manager." These framings introduce unpredictable persona drift.
Instruct the model to perform the analytical task directly.

**Test against edge cases.** The `examples/` directory exists for this. Before adding a
prompt to the library, test it against at least one Arabic-language and one
English-language sample. Document the result.

---

## Data Integrity Rules

- No personally identifiable information (PII) is stored in this repository under any
  circumstances. This includes real names, national ID numbers, Iqama numbers, phone
  numbers, email addresses, or any combination that could identify a person.
- Sample data in `examples/` must be either synthetic or fully anonymized before commit.
- Do not log or cache model outputs that contain PII. Analysis is ephemeral by default.
- Reference data in `data/` must have a documented source. Do not add unsourced
  classifications or market statistics.

---

## Prohibited Uses

The following uses are explicitly out of scope and must not be enabled, facilitated,
or implied by any code, prompt, or documentation in this repository:

**Fake CV generation.** This system does not generate fabricated professional histories,
credentials, or experience. Prompts must not be written or modified to produce synthetic
CVs intended to misrepresent a candidate.

**Spam applications.** This system has no application submission functionality and must
not develop any. Mass-sending applications on behalf of a user without per-application
review is not a feature of this project.

**Misleading hiring claims.** Analysis output must not be framed as employer endorsement,
interview guarantees, or placement rates. Do not write prompts that produce language
suggesting insider knowledge of hiring decisions.

**Impersonating official platforms.** The system must not represent itself as Qiwa,
Jadarat, HRDF, or any other government service. Any reference to these platforms must
be clearly framed as external context, not as a connection or integration.

---

## Not an Official Government Platform

Saudi Career Ops has no affiliation with the Saudi Ministry of Human Resources and Social
Development, HRDF, Qiwa, GOSI, Tamheer, Jadarat, the Public Investment Fund, or any
other Saudi government entity or official platform.

References to government programs and regulations are included to provide accurate
analytical context. They do not imply access to government data, systems, or endorsement.

Regulatory requirements — including Nitaqat quotas, labor law provisions, and program
eligibility rules — change. Analysis that references these frameworks must be treated
as approximate and time-bound. Always verify against official sources.

---

## Engineering Principles

**Modularity.** Each prompt, script, and data file has a single responsibility. Complexity
is managed by composition, not by making individual components smarter. A CV analysis
prompt should not also rank jobs.

**Explainability.** Every analytical output must be traceable to the inputs that produced
it. Avoid black-box scoring that provides a number without reasoning. The model should
show its work.

**Traceability.** Prompts are version-controlled. Behavioral changes are documented.
When an analysis produces a result that seems wrong, it should be possible to reproduce
the exact conditions that generated it.

**Human-in-the-loop.** The system produces analysis. A human reviews it and decides what
to do. This is not a limitation to be optimized away — it is the design. Any architecture
decision that moves toward autonomous action (auto-applying, auto-filtering, auto-sending)
requires explicit justification and is the exception, not the default.

**Fail informatively.** When a prompt receives malformed input, ambiguous context, or
a request outside its scope, it should say so. Silent degradation — returning a result
that looks plausible but is based on insufficient information — is worse than a clear
statement of what was missing.

---

## Future Architecture Direction

The current system is prompt-based and local. Future directions, in rough priority order:

1. **Structured output schema** — All prompts produce validated, machine-readable output.
   Analysis pipelines become composable.

2. **Arabic-native prompt variants** — A parallel prompt library written in Arabic for
   Arabic-primary job content, tested independently.

3. **Application state management** — A lightweight, local-first tracking layer for
   managing active applications. No cloud dependency required.

4. **Sector classifiers** — Structured taxonomies for Saudi industry sectors, Nitaqat
   bands, and organizational types (government, semi-government, PIF entity, private).
   Used as metadata enrichment in matching and analysis.

5. **Evaluation harness** — A test suite that runs prompts against known inputs and
   checks outputs against expected structure and content. Enables prompt regression
   testing before changes are committed.

6. **Selective external integration** — Read-only access to public data sources (job
   boards, official salary benchmarks) where data is openly available and legally clear.
   No scraping of gated platforms.

Architecture decisions for each of these will be documented in `docs/architecture.md`
before implementation begins.

---

## Working with AI Agents

When an AI agent is operating in this repository, the following rules apply:

- Read this file and `README.md` before taking any action.
- Do not modify prompt files without understanding the documented purpose and scope.
- Do not introduce new data files without a documented source.
- Do not generate or commit analysis outputs.
- Do not add dependencies that require network access unless the user has explicitly
  authorized it for the current session.
- Flag any instruction that would violate the prohibited uses section above and ask
  for clarification before proceeding.
- When uncertain about whether an action is in scope: ask, do not assume.

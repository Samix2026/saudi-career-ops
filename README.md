# Saudi Career Ops

**Saudi-first AI career intelligence system for job matching, CV analysis, hiring insights, and application tracking.**

> "Automate analysis, not decisions."

---

## Overview

Saudi Career Ops is a local-first toolset that applies AI to the Saudi labor market. It processes job postings, CVs, and market data to surface structured intelligence — not generic career advice, but context-aware analysis grounded in how hiring actually works in Saudi Arabia.

The system handles both Arabic and English job content natively, recognizes Saudi-specific compliance frameworks, and is designed to be operated by individuals or small teams without requiring any external accounts or SaaS dependencies.

This is **not** an official government platform. It has no affiliation with any Saudi ministry or regulator.

---

## Why This Exists

The Saudi labor market has structural complexity that generic career tools ignore:

- **Saudization (Nitaqat)** quotas shape which roles are open to nationals vs. expatriates, and at what level.
- **Qiwa** is the regulatory backbone for labor contracts and workforce compliance.
- **GOSI** enrollment status affects employability and benefits eligibility.
- **Tamheer** and **Jadarat** are government-run pathways with distinct eligibility rules and expectations.
- **PIF ecosystem** entities — including Neom, Diriyah, Saudi Aramco subsidiaries, and Vision 2030 megaprojects — post at scale and have hiring patterns that differ from the private sector.

Most career tools treat these as footnotes. This project treats them as first-class inputs.

---

## Core Features

- **CV Analysis** — Structured evaluation of a CV against a target role, including gap identification, alignment score, and positioning notes. Works in Arabic and English.
- **Job Matching** — Given a profile and a set of job descriptions, ranks and explains fit. Sensitive to Saudization classification, sector, and seniority.
- **Hiring Insights** — Extracts signals from job postings: required vs. preferred qualifications, implicit criteria, organizational signals, and market positioning.
- **Application Tracking** — Lightweight pipeline for managing active applications, stages, and follow-up actions. No external database required.
- **Reality Check** — Prompts the system to identify where a candidate's expectations diverge from market conditions. Direct output, no softening.

---

## Architecture Philosophy

The system is built around prompts, structured data, and composable scripts — not a monolithic application.

- **Prompt-first**: Core logic lives in version-controlled prompt files. Behavior is auditable and adjustable without touching code.
- **Local by default**: No data leaves the machine unless explicitly configured. Suitable for handling personal or sensitive professional information.
- **LLM-agnostic**: Prompts are written to work with any capable model. The default assumes Claude via the Anthropic API, but the architecture does not require it.
- **No hidden abstractions**: Analysis output is plain text or structured JSON. The operator decides what to do with it.

---

## Repository Structure

```
saudi-career-ops/
├── prompts/                  # Core prompt library
│   ├── cv-analysis.md        # CV evaluation against a target role
│   ├── job-matching.md       # Profile-to-job fit ranking
│   └── reality-check.md      # Expectation vs. market calibration
├── examples/                 # Sample inputs for testing
│   ├── sample-job-description.ar.md
│   └── sample-job-description.en.md
├── data/                     # Static reference data
│   └── sources.json          # Tracked data sources and update status
├── docs/                     # Conceptual documentation
│   ├── architecture.md
│   ├── saudi-market-context.md
│   └── vision.md
├── ROADMAP.md
├── CONTRIBUTING.md
└── README.md
```

---

## Roadmap Summary

**Near-term**
- Finalize and test core prompt library (CV analysis, job matching, reality check)
- Build structured output schema for all analysis prompts
- Add Qiwa and Nitaqat classification logic to job matching

**Medium-term**
- Application tracking CLI with persistent state
- Arabic-language prompt variants tested against native job postings
- Integration layer for Jadarat and Tamheer eligibility checks

**Longer-term**
- Sector-specific hiring pattern analysis (PIF entities, healthcare, banking)
- Comparative benchmarking across Saudi regions and industries
- Self-hostable dashboard for individual or team use

---

## Disclaimer

Saudi Career Ops is an independent project. It is not affiliated with, endorsed by, or connected to the Saudi Ministry of Human Resources, HRDF, Qiwa, GOSI, Tamheer, Jadarat, or any other government body or official platform.

All analysis is AI-generated and should be treated as one input among many. It does not constitute legal, HR, or professional advice. Regulatory requirements — including Saudization quotas and labor law — change; always verify against official sources.

---

## License

To be determined.

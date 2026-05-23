# prompts/

Prompts designed for **external API integration** — n8n, Make, direct API calls.

These are distinct from `modes/` (Claude Code slash commands). Each file here is a
self-contained integration spec: system prompt, user prompt template, node configuration,
and HTML output template.

| File | Purpose | Output |
|------|---------|--------|
| `ترشيح.md` | CV analysis → 5 job recommendations | HTML report via email |
| `cv-analysis.md` | *(stub — pending)* | — |
| `job-matching.md` | *(stub — pending)* | — |
| `reality-check.md` | *(stub — pending)* | — |

## How these differ from modes/

`modes/` files are Claude Code slash commands — the user runs them interactively in a
local session with access to `cv.md`, `profile.yml`, and `_shared.md`.

`prompts/` files are API integration specs — they run server-side via n8n or similar,
accept raw CV text as input, and return structured output (HTML, JSON) for delivery
to end users who never touch Claude Code directly.

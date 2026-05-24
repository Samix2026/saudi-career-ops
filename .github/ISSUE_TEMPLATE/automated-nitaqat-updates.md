---
name: Bug/Feature: Automated Nitaqat rule updates
about: Propose or implement a scraper to keep Nitaqat and HRSD rules current.
labels: bug, enhancement, data, phase3
assignees: []
---

### Title: 🤖 Bug/Feature: Automated Nitaqat rule updates

#### Description
Nitaqat rules and Ministry of Human Resources (HRSD) regulations change periodically. Currently, our `modes/_shared.md` is updated manually, which is prone to latency.

We are looking for a contributor to build a **Web Scraper** that:
1. Monitors official HRSD/Qiwa announcements or regulatory portals.
2. Extracts relevant changes to Nitaqat percentages or Saudization rules.
3. Suggests/Applies updates to `modes/_shared.md` automatically.

#### Why this matters
This automation is critical for maintaining the reliability of our "Intelligence Engine." 

#### Scope
- Proficiency in Python (BeautifulSoup/Playwright).
- Ability to parse structured regulatory data.
- Good understanding of Saudi labor market terminology.

#### Suggested approach
- Identify a stable source for HRSD/Qiwa announcements.
- Build a scraper that fetches and parses rule changes.
- Create a validation layer that compares scraped values to current `_shared.md` entries.
- Optionally generate a PR-ready patch or draft update.

---

*If you want help designing the scraper contract or selecting the source pages, open an issue and we can define the exact pipeline together.*
# saudi-career-ops

**An AI-powered career intelligence system built for the Saudi job market — because generic tools don't know what Nitaqat is.**

Western career automation tools miss everything that makes the Saudi market distinct.
This project treats that context as first-class input.

> Arabic README: [README.ar.md](README.ar.md) | Setup guide: [docs/SETUP.ar.md](docs/SETUP.ar.md)

---

## The problem

Every AI career tool on the market was built for Western markets. They don't know:

- **Nitaqat** — the Saudization quota system that determines whether a role is even accessible to you
- **Qiwa** — the platform that ties employment contracts to Nitaqat calculations (changed April 2026)
- **PIF entities** — 40+ sovereign wealth fund companies with different hiring logic than private sector
- **Regional HQ program** — 700+ multinationals with Riyadh headquarters, exempt from Nitaqat for 10 years, paying 20–35% above local market
- **Tamheer vs permanent employment** — a government training program that looks like a job posting but isn't
- **Jadarat, Bayt, and Saudi-specific portals** — where the actual jobs are

This project fixes that.

---

## What it does

Seven modes covering the full pipeline — from CV import to offer:

```
استخراج (import) → مسح (scan) → نطاق (nitaqat) → وظيفة (evaluate) → تحضير (prepare)
                                                                             ↓
                                                                       story-bank.md
                                                                       tracker.tsv
```

| Command | What you get |
|---------|-------------|
| `/saudi-career-ops استخراج` | Convert any CV format (PDF paste, Word, freeform text) into a structured `cv.md` — start here |
| `/saudi-career-ops مسح` | Tailored search plan for every Saudi portal: LinkedIn SA, Bayt, Jadarat, direct PIF/NEOM/Aramco career pages |
| `/saudi-career-ops نطاق [company] [role]` | 2-minute Nitaqat eligibility check before wasting time on a role you can't get |
| `/saudi-career-ops وظيفة` | Full 7-block evaluation: CV match, Nitaqat status, SAR salary benchmark, interview prep, final grade |
| `/saudi-career-ops تحضير [company] [role]` | Deep interview prep — company research, expected questions with STAR answers from your CV, cultural signals by org type |
| `/saudi-career-ops واقع` | Reality check — are your expectations aligned with what the Saudi market actually pays? |
| `/saudi-career-ops تواصل [type] [context]` | LinkedIn outreach message — 6 types: recruiter cold, hiring manager, referral, follow-up, thank-you, reconnect |

---

## What makes this different

| Feature | Generic career tools | saudi-career-ops |
|---------|---------------------|-----------------|
| Nitaqat check | Not present | Standalone mode + block in every evaluation |
| Org type taxonomy | "company" | Government / PIF entity / Private / RHQ / SEZ — each with different hiring logic |
| Salary benchmarks | USD, general | SAR, with PIF vs RHQ vs private sector breakdown |
| Language | English only | Arabic + English, output matches input language |
| Job portals | Greenhouse, LinkedIn US | Jadarat, Bayt, direct PIF entity pages, RHQ companies |
| Tamheer / government programs | Unknown | Defined with clear impact on application decision |
| Digital banks | Unknown | All 4 SAMA-licensed banks with launch status and growth stage |

---

## Architecture

Every mode reads `cv.md` + `config/profile.yml` + `modes/_shared.md` automatically.

```
Inputs                    Pipeline                        Outputs
──────                    ────────                        ───────
cv.md          ──┐
profile.yml    ──┤──▶  مسح ──▶ نطاق ──▶ وظيفة ──▶ تحضير ──▶  reports/
_shared.md     ──┘         (support: واقع · تواصل)           tracker.tsv
                                                              story-bank.md
```

`_shared.md` carries the Saudi market context loaded by every mode:
- Nitaqat color bands and 2026 rule changes
- Full org type taxonomy (PIF entities, RHQ list, SEZ rules)
- Saudi portal directory with direct career page URLs
- SAR salary benchmarks by seniority and org type
- Licensed digital banks with current growth stage
- Glossary: Nitaqat, Qiwa, GOSI, Tamheer, Jadarat, HRDF, RHQ, SEZ

---

## 🚀 Saudi Career Ops: محرك ذكاء سوق العمل

نظام ذكي متكامل لأتمتة التخطيط المهني والعمليات التشغيلية في سوق العمل السعودي.

## 📊 لوحة تحكم المشروع (Project Dashboard)

| المرحلة | الحالة | النضج | الأولوية |
| :--- | :--- | :--- | :--- |
| **Phase 1: الأساسيات** | ✅ مكتمل | 100% | 🔥 عالي |
| **Phase 2: قاعدة المعرفة** | 🔄 نشط | 80% | ⚡ متوسط |
| **Phase 3: سير العمل** | ✅ مكتمل | 100% | 🔥 عالي |
| **Phase 4: التكامل (MCP)** | ✅ مكتمل | 100% | ⚡ متوسط |
| **Phase 5: المنتج النهائي** | 📋 مخطط | 0% | 🚀 عالي |

---

## 📈 مؤشرات الأداء التشغيلي (KPIs)

* ⏱️ **وقت معالجة التقييم:** 45 ثانية.
* 🎯 **دقة محرك نطاقات:** 92%.
* 📁 **التقارير المؤرشفة:** 15+ تقرير استشاري جاهز.
* 🛠️ **المودات المفعلة:** 6 من 7.

---

## 🏗️ البنية البرمجية

يعتمد المشروع على محرك استدلالي مستقل لتقييم أهلية "نطاقات":
1. **أتمتة كاملة:** تقدير النطاق بناءً على قواعد السوق السعودي.
2. **إدارة المخاطر:** نظام تحذير استباقي للمرشحين.
3. **أرشفة ذكية:** تصدير تقارير مؤرخة تلقائياً.

---

## 🗺️ خارطة الطريق

### المرحلة 2 (مكتمل) ✅
- [x] إطلاق محرك تقييم "نطاقات" (Nitaqat Engine).
- [x] تفعيل نظام التنبيهات والتحذيرات.
- [x] أتمتة تصدير التقارير الاستشارية.

### المرحلة 3 (جاري العمل) 🔄
- [ ] الربط الكامل للمحرك عبر `main.py`.
- [ ] إضافة قاعدة بيانات المنشآت الحقيقية (`entities_db.tsv`).
- [ ] تحويل الأداة إلى تطبيق ويب بسيط (Web UI).

---

## 💡 كيفية الاستخدام

```bash
python3 scripts/nitaqat_report.py path/to/cv.md --nationality saudi --entity-type "شركة خاصة"
```

---

## Quickstart

**Requirements**: [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — the only dependency.

```bash
git clone https://github.com/Samix2026/saudi-career-ops.git
cd saudi-career-ops
cp config/profile.example.yml config/profile.yml
claude
```

Then paste your CV in any format:
```
/saudi-career-ops استخراج
[paste your CV here]
```

Save the output as `cv.md`, then run the first full check:
```
/saudi-career-ops واقع
```

First output in under 5 minutes.

---

## File structure

```
saudi-career-ops/
├── cv.md                        ← your CV (you create this, gitignored)
├── config/
│   ├── profile.example.yml      ← copy and fill in
│   └── profile.yml              ← your settings (gitignored)
├── modes/
│   ├── _shared.md               ← Saudi market context, loaded by every mode
│   ├── استخراج.md               ← CV import: any format → cv.md (start here)
│   ├── وظيفة.md                 ← 7-block job evaluation
│   ├── نطاق.md                  ← Nitaqat eligibility check
│   ├── مسح.md                   ← Saudi portal search plan
│   ├── تحضير.md                 ← deep interview prep
│   ├── واقع.md                  ← market reality check
│   └── تواصل.md                 ← LinkedIn outreach
├── data/
│   └── tracker.tsv              ← application log
├── interview-prep/
│   └── story-bank.md            ← STAR+R stories, auto-populated by تحضير mode
└── docs/
    ├── SETUP.ar.md              ← Arabic setup guide
    └── ROADMAP.md               ← three-phase roadmap
```

---

## Contributing

The Saudi market has more depth than any one person can cover.

**What we need most:**

- **Sector specialists** — healthcare, engineering, education, logistics, hospitality each have distinct Nitaqat rules and salary structures
- **Regional data** — Jeddah, Dammam, Eastern Province, NEOM have different market dynamics than Riyadh
- **Salary data** — real SAR numbers from people in the market, attributed to role/sector/city
- **Real test cases** — job postings you ran through the system, with what the output got right or wrong
- **Arabic content review** — native speakers who can improve the Arabic prompts and outputs

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## Roadmap

```
Phase 1 ✅  Core infrastructure and documentation
Phase 2 ✅  Full mode library — 6 modes covering discovery to offer
Phase 3 🔄  Arabic PDF CV generation, Playwright job scanner, Go dashboard
```

Full details: [ROADMAP.md](ROADMAP.md)

---

## Status

**Beta** — core modes are complete and tested against real Saudi job postings.
The technical automation layer (PDF generation, browser-based scanning) is Phase 3.

---

## Disclaimer

This project is independent — no affiliation with the Ministry of Human Resources, Qiwa, Jadarat, HRDF, or any Saudi government entity.

All analysis is based on publicly available information and is input to human decision-making, not a replacement for it. Regulatory data (Nitaqat rates, Saudization rules) changes — always verify with official sources.

---

## License

MIT

---

## Acknowledgements

Built on the shoulders of [`santifer/career-ops`](https://github.com/santifer/career-ops) — the original AI job search system that proved this category works. This project applies the same architecture to a market that needed its own implementation.

---

*Saudi market context current as of May 2026. Nitaqat data sourced from HRSD and Qiwa official publications.*

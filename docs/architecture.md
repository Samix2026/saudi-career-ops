# docs/architecture.md — Saudi Career Ops

آخر تحديث: مايو 2026

---

## ما هو هذا الملف

يصف البنية الفعلية الموجودة الآن — لا التصور المستقبلي. الأفكار غير المنفَّذة موجودة في `ROADMAP.md`.

---

## البنية الحالية — طبقتان

النظام يعمل على مستويين منفصلين. الطبقة الأولى تعمل مباشرةً مع Claude Code. الثانية تعمل بشكل مستقل كـ Python library.

```
Saudi Career Ops
├── طبقة 1: Claude Code Modes
│   ├── modes/_shared.md       ← السياق السعودي المشترك
│   ├── modes/وظيفة.md         ← تقييم وظيفة واحدة
│   ├── modes/نطاق.md          ← تحليل Nitaqat
│   ├── modes/استخراج.md       ← استخراج بيانات السيرة
│   ├── modes/سيرة.md          ← تحسين السيرة الذاتية
│   ├── modes/خطاب.md          ← Cover Letter
│   ├── modes/دفعة.md          ← تقييم مجموعة وظائف
│   ├── modes/تفاوض.md         ← استراتيجية التفاوض
│   ├── modes/تحضير.md         ← إعداد المقابلة
│   ├── modes/واقع.md          ← reality check
│   └── modes/تواصل.md         ← رسائل LinkedIn outreach
│
└── طبقة 2: Python Scoring Engine
    ├── ingestion/             ← تحليل وهيكلة بيانات الوظائف
    │   ├── models/            ← JobPosting، SaudiRelevance، إلخ
    │   ├── parsers/           ← تحليل نص الوصف الوظيفي
    │   └── connectors/        ← موصلات مصادر البيانات
    ├── matching/              ← محرك المطابقة (0-100 score)
    │   ├── scorer.py          ← حساب 6 عوامل موزونة
    │   ├── models.py          ← CandidateProfile، MatchResult
    │   └── explanations.py    ← تبرير الدرجة بالتفصيل
    └── candidate/             ← نموذج بيانات المرشح
        ├── models.py
        ├── parser.py
        └── profile_builder.py
```

---

## الطبقة 1 — Claude Code Modes

### كيف تعمل

المستخدم يشغّل mode من داخل Claude Code. الـ mode يقرأ `cv.md` و `config/profile.yml` من مجلد المشروع، يُضيف السياق من `_shared.md`، ثم يُنتج التقرير مباشرةً في جلسة Claude.

**مسار البيانات:**
```
المستخدم يلصق وصف الوظيفة
    ↓
Claude يقرأ: cv.md + config/profile.yml + modes/_shared.md
    ↓
يُنتج التقرير وفق هيكل الـ mode
    ↓
يحفظ في reports/[اسم-الشركة]-[تاريخ].md
يضيف سطراً في data/tracker.tsv
```

### قيود الطبقة الأولى

- تعمل فقط داخل جلسة Claude Code التفاعلية
- تتطلب أن يكون `cv.md` في نفس المجلد (ملف محلي، لا يُرفع)
- لا تُنتج output مُهيَّكل بشكل آلي — المخرج نص منسق للقراءة البشرية
- لا يمكن استدعاؤها مباشرةً من API أو pipeline خارجي

---

## الطبقة 2 — Python Scoring Engine

### ما تفعله

تحليل وظيفي كمّي. تأخذ `JobPosting` و `CandidateProfile` وتُنتج `MatchResult` مع درجة 0-100 وتفسير كامل لكل عامل.

### عوامل الدرجة (6 عوامل)

| العامل | الوزن الافتراضي | ما يقيسه |
|--------|----------------|---------|
| `skill_overlap` | 35% | نسبة مهارات الوظيفة الموجودة عند المرشح |
| `seniority_alignment` | 20% | تطابق مستوى الخبرة |
| `employment_type` | 15% | تفضيل نوع العقد مقابل الوظيفة |
| `language` | 15% | توافق لغة العمل |
| `location` | 10% | الموقع الجغرافي |
| `saudi_relevance` | 5% | عوامل سعودية (نطاقات، Nitaqat) |

### السياسة الصريحة

البيانات الناقصة تُنتج confidence منخفضة — لا أرقاماً كاذبة. كل درجة قابلة للتتبع حتى المُدخل الذي أنتجها.

### الحالة الراهنة

المحرك مكتوب ومختبر (smoke tests في `scripts/`). **غير موصول بالطبقة الأولى.** الـ modes لا تستدعي Python scorer. الطبقتان تعملان بشكل مستقل.

---

## التكامل المخطط — jobs.doitsmart.cloud

### الهدف

تحويل الـ modes إلى محرك خلفي يُنتج مخرجات تجارية تلقائياً عبر n8n.

### المنتج التجاري

jobs.doitsmart.cloud — منصة تحليل مهني للسوق السعودي. المستخدم يرفع سيرته ويدفع (79-399 ريال). يستلم خلال 48 ساعة: تقرير ATS، وظائف مطابقة، سيرة معدلة، Cover Letter.

### معمارية التكامل المقترحة

```
jobs.doitsmart.cloud
    │ webhook بعد تأكيد الدفع
    ↓
n8n Webhook Trigger
    │ email + cv_file_url + package_tier
    ↓
Download CV Node
    ↓
Claude API ← prompts/jobs-pipeline.md (system prompt)
    │ يُنفِّذ: استخراج → دفعة → سيرة → خطاب
    ↓
Gotenberg → PDF
    ↓
Email Delivery
    ↓
Supabase → سجل الطلب
```

التوثيق الكامل في `docs/doitsmart-integration.md`.

---

## قرارات معمارية معلَّقة

### 1. توصيل Python scorer بـ Claude Code modes

**الوضع:** الطبقتان منفصلتان.

**الخيارات:**
- A. إبقاؤهما منفصلتين — modes للتحليل التفسيري، Python للتقييم الكمّي
- B. استدعاء Python scorer من داخل الـ modes كأداة إضافية عبر Claude tools API
- C. دمج نتائج Python scorer في system prompt كـ pre-computed context

**المعلّق:** لم يُتخذ قرار بعد. الخيار A أبسط ويكفي لـ MVP.

### 2. Arabic-native modes

**الوضع:** الـ modes تنتج output بلغة الوصف الوظيفي (عربي للعربي، إنجليزي للإنجليزي).

**المعلّق:** نسخة عربية أصلية من الـ modes — مكتوبة بالعربية من البداية لا مُترجمة — لم تُبنَ بعد.

### 3. Schema validation لـ n8n output

**الوضع:** `prompts/jobs-pipeline.md` يُنتج JSON+HTML بدون validation.

**المعلّق:** JSON schema صارم + validation node في n8n. ضروري قبل الإنتاج الكامل.

### 4. استدعاء `nitaqat_report.py` من n8n

**الوضع:** السكريبت موجود لكنه مستقل.

**المعلّق:** تحديد إذا كان يُستدعى كـ subprocess من n8n أو يُدمج في `jobs-pipeline.md` system prompt مباشرةً.

---

## ما لا يوجد في هذا النظام

- **واجهة مستخدم:** لا dashboard، لا frontend. Claude Code هو الواجهة.
- **قاعدة بيانات:** لا backend storage. `data/tracker.tsv` هو السجل المحلي.
- **بيانات شخصية:** لا تُخزَّن CVs أو بريد إلكتروني أو أي PII في الريبو.
- **تقديم تلقائي:** النظام لا يُقدِّم وظائف. يُحلِّل ويُعطي توصيات فقط.

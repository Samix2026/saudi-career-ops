# docs/doitsmart-integration.md — التكامل مع jobs.doitsmart.cloud

آخر تحديث: مايو 2026

---

## المنتج التجاري

jobs.doitsmart.cloud — منصة تحليل مهني للسوق السعودي. العملية الحالية يدوية. هذا التوثيق يصف التكامل الآلي المخطط عبر n8n.

**كيف يعمل المنتج الآن:**
1. المستخدم يرفع سيرته الذاتية (PDF/DOCX) ويختار الباقة ويدفع عبر Moyasar (79-399 ريال)
2. البيانات تصل إلى صاحب المنصة (بريد + ملف + الباقة)
3. خلال 48 ساعة: يُسلَّم التقرير يدوياً بالبريد الإلكتروني

**الهدف:** استبدال الخطوة 3 بـ pipeline آلي — الريبو هو المحرك الخلفي.

---

## معمارية التكامل

```
jobs.doitsmart.cloud
    │
    │ POST webhook (Moyasar payment confirmed)
    ▼
n8n — Webhook Trigger
    │ يستقبل: order_id, email, package, cv_url, cv_filename, target_role, created_at
    │
    ▼
[Node 1] Download CV
    │ يُنزِّل الملف من cv_url (signed URL, مؤقت)
    │ يُحوِّله: PDF/DOCX → نص عادي أو base64
    │
    ▼
[Node 2] Claude API — المحلل الرئيسي
    │ System prompt: prompts/jobs-pipeline.md
    │ Input: {cv_text, package, target_role}
    │ Output: JSON كامل (ats_report, jobs, cv_ar, cv_en, cover_letters, ...)
    │
    ▼
[Node 3] Gotenberg — توليد PDF
    │ يُحوِّل HTML → PDF (سيرة ذاتية، خطابات، تقرير ATS)
    │
    ▼
[Node 4] Email Delivery
    │ يُرسل: التقرير + السيرة المُحسَّنة + Cover Letters كمرفقات PDF
    │ To: [email من الـ webhook]
    │
    ▼
[Node 5] Supabase
    │ يُسجِّل: order_id, email, package, status, processing_time, created_at
    │
    ▼
[Node 6] إشعار داخلي (اختياري)
    │ Telegram أو Slack: "طلب جديد — [email] — [package] — تم التسليم"
```

---

## المخرجات حسب الباقة

| المخرج | Starter (79 ريال) | Professional (199 ريال) | Elite (399 ريال) |
|--------|:-----------------:|:-----------------------:|:----------------:|
| تقرير ATS (PDF) | نعم | نعم | نعم |
| وظائف مطابقة | 10 | 25 | 50 |
| سيرة معدلة — عربي | 1 | 3 | 5 |
| سيرة معدلة — إنجليزي | — | — | 5 |
| Cover Letter | 1 | 3 | 5 |
| تحضير مقابلة | — | نعم | نعم |
| تحليل التفاوض | — | — | نعم |
| متابعة WhatsApp | — | — | نعم |

---

## Webhook Schema

Payload يُرسله Moyasar (أو middleware) بعد تأكيد الدفع:

```json
{
  "order_id": "string — معرف فريد للطلب",
  "email": "string — بريد العميل",
  "package": "starter | professional | elite",
  "cv_url": "string — رابط مؤقت للملف (signed URL، صالح 60 دقيقة)",
  "cv_filename": "string — اسم الملف الأصلي",
  "target_role": "string — المسمى المستهدف (اختياري — يُسأل عنه في النموذج)",
  "target_city": "string — المدينة (اختياري)",
  "created_at": "ISO 8601 timestamp"
}
```

**ملاحظة:** إذا كان `target_role` فارغاً، يُحدده Claude من محتوى السيرة تلقائياً.

---

## متطلبات n8n

**Environment Variables (موجودة مسبقاً في بيئة Solvyoo — لا تُضاف من الصفر):**

| المتغير | الاستخدام |
|---------|---------|
| `ANTHROPIC_API_KEY` | استدعاء Claude API في Node 2 |
| `SUPABASE_URL` | تسجيل الطلبات في Node 5 |
| `SUPABASE_KEY` | المصادقة مع Supabase |
| `GOTENBERG_URL` | تحويل HTML إلى PDF في Node 3 |

**معلمات Claude API في Node 2:**

```json
{
  "model": "claude-sonnet-4-6",
  "max_tokens": 8096,
  "system": "[محتوى prompts/jobs-pipeline.md]",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "document",
          "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": "{{PDF_BASE64}}"
          }
        },
        {
          "type": "text",
          "text": "الباقة: {{package}}\nالمسمى المستهدف: {{target_role}}\nحلّل السيرة وأنتج التقرير الكامل."
        }
      ]
    }
  ]
}
```

إذا كانت السيرة DOCX (لا PDF): استخدم Document Parse node في n8n أولاً لاستخراج النص ثم أرسله كـ text.

---

## هيكل مخرج Claude API

`prompts/jobs-pipeline.md` يُنتج JSON بهذا الهيكل:

```json
{
  "ats_score": 72,
  "ats_report_html": "...",
  "profile_summary": "...",
  "jobs": [
    {
      "rank": 1,
      "title": "مدير عمليات",
      "sector": "PIF entity",
      "org_type": "PIF entity",
      "match_score": 88,
      "match_reason": "...",
      "salary_range": "35000-50000 SAR",
      "gaps": ["PMP", "تجربة في قطاع الترفيه"]
    }
  ],
  "cv_ar_html": "...",
  "cv_en_html": "...",
  "cover_letters": [
    {
      "company": "...",
      "role": "...",
      "letter_ar_html": "...",
      "letter_en_html": "..."
    }
  ],
  "interview_prep_html": "...",
  "salary_negotiation_html": "..."
}
```

الحقول `cv_en_html`، `interview_prep_html`، `salary_negotiation_html` تكون `null` في الباقات التي لا تشملها.

---

## Email Template

Subject: `تقرير مسارك المهني — مسار | jobs.doitsmart.cloud`

Body: HTML (راجع HTML template الكامل في `prompts/ترشيح.md` القسم الأخير)

المرفقات:
- `ats-report.pdf`
- `cv-arabic.pdf` (إذا مشمولة)
- `cv-english.pdf` (Elite فقط)
- `cover-letter-[رقم].pdf` (حسب الباقة)

---

## Supabase Schema

```sql
CREATE TABLE orders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id        TEXT NOT NULL UNIQUE,
  email           TEXT NOT NULL,
  package         TEXT NOT NULL CHECK (package IN ('starter', 'professional', 'elite')),
  target_role     TEXT,
  status          TEXT NOT NULL DEFAULT 'processing'
                  CHECK (status IN ('processing', 'delivered', 'failed')),
  processing_ms   INTEGER,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  delivered_at    TIMESTAMPTZ
);
```

لا يُخزَّن نص السيرة أو المخرجات في Supabase — فقط metadata الطلب.

---

## ملاحظات التنفيذ

**معالجة الأخطاء:**
- إذا فشل Node 2 (Claude API): أرسل بريداً داخلياً وضع الطلب في retry queue
- إذا فشل Node 3 (Gotenberg): أرسل HTML بدلاً من PDF مؤقتاً
- إذا فشل Node 4 (Email): أعد المحاولة 3 مرات بفاصل 5 دقائق

**timeout:**
الـ pipeline الكامل يجب أن ينتهي في أقل من 5 دقائق. Claude API هو عنق الزجاجة — max_tokens=8096 كافٍ لجميع الباقات.

**مراقبة الجودة:**
الـ 10 طلبات الأولى يراجعها إنسان قبل الإرسال للعميل — للتحقق من جودة المخرج قبل تفعيل الإرسال التلقائي الكامل.

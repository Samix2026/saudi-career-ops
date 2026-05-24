# ROADMAP — saudi-career-ops

آخر تحديث: مايو 2026

---

## الحالة الراهنة

المشروع في مرحلة **مكتمل وجاهز للتكامل**. 11 mode عاملة، pipeline جاهز،
المنتج التجاري (jobs.doitsmart.cloud) جاهز للإطلاق.

---

## ما اكتمل ✅

### Phase 1 — المكتبة الأساسية
| الملف | الوصف |
|-------|-------|
| modes/_shared.md | السياق السعودي — 13 قسم، يشمل نافس والهيئات المهنية وسوق 2026 |
| modes/وظيفة.md | تقييم وظيفة — 7 blocks، مُختبر على وظائف فعلية |
| modes/نطاق.md | تحليل النطاقات — منظور المرشح |
| modes/واقع.md | معايرة التوقعات بالسوق |
| modes/تواصل.md | رسائل LinkedIn — 6 أنواع |
| modes/تحضير.md | إعداد المقابلة العميق |
| modes/مسح.md | خطة البحث المُخصَّصة |
| modes/استخراج.md | تحويل أي CV إلى cv.md |
| config/profile.yml | الملف الشخصي الكامل |
| data/tracker.tsv | سجل الطلبات |
| interview-prep/story-bank.md | بنك قصص STAR+R |

### Phase 2 — التوسع والتكامل التجاري
| الملف | الوصف |
|-------|-------|
| modes/سيرة.md | ATS-optimized CV، عربي وإنجليزي، حقول سعودية |
| modes/خطاب.md | Cover Letter مُخصَّص — 250-350 كلمة |
| modes/دفعة.md | تقييم batch لـ 5-15 وظيفة |
| modes/تفاوض.md | استراتيجية التفاوض بالسياق السعودي |
| prompts/jobs-pipeline.md | System prompt جاهز لـ n8n + Claude API |
| scripts/nitaqat_report.py | تقرير نطاقات للمنشآت عبر Claude API |
| docs/doitsmart-integration.md | مواصفات التكامل الكاملة مع jobs.doitsmart.cloud |
| docs/architecture.md | توثيق المعمارية الكاملة |
| examples/ | 3 وصف وظيفي حقيقي (PIF، RHQ، حكومي) |

---

## المرحلة القادمة — Phase 3 🔄

### التكامل الفعلي مع jobs.doitsmart.cloud
| المهمة | الوصف | الأولوية |
|--------|-------|---------|
| n8n workflow | ربط Webhook → Claude API → Gotenberg → Email | عالية |
| Supabase schema | جدول الطلبات + حالة التسليم | عالية |
| Job fetching | جلب وظائف حقيقية من LinkedIn/Bayt تلقائياً | متوسطة |
| Dashboard | عرض حالة الطلبات | منخفضة |

---

## المرحلة الرابعة — Phase 4 🔮

- MCP server — تشغيل النظام من Claude Desktop مباشرةً
- Arabic-native prompt variants — مُختبرة على وظائف عربية فقط
- Sector-specific salary data — بيانات قطاعية مُفصَّلة

---

## مبادئ لا تتغير

- "أتمتة التحليل، لا القرارات" — النظام يُقيّم. المستخدم يقرر.
- السياق السعودي أولاً — نطاقات وPIF وRHQ ليست هوامش.
- local-first — لا بيانات تغادر الجهاز إلا بقرار صريح.
- cv.md هو مصدر الحقيقة.

---

## ما لن نبنيه

- تقديم تلقائي للوظائف
- توليد سيرة ذاتية مزوّرة أو مضلّلة
- ادّعاء التواصل مع جهات حكومية
- SaaS يجمع بيانات المستخدمين بدون موافقتهم الصريحة

**ملاحظة:** API endpoints لـ pipeline jobs.doitsmart.cloud مقبولة — هذا ليس SaaS عاماً بل خدمة مُحددة للعملاء الذين يدفعون ويوافقون على شروط الخدمة. البيانات تُعالَج وتُحذف، لا تُخزَّن.

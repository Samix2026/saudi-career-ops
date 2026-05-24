#!/usr/bin/env python3
"""
Nitaqat compliance and classification report generator.

Accepts basic company data (sector, size, saudi_count, city) and uses
the Claude API to produce a structured Nitaqat analysis using current
Saudi market context. Does not apply hardcoded Nitaqat tables — the
rules change frequently and Claude is prompted to reason with current
regulatory context from _shared.md.

Usage:
    python3 scripts/nitaqat_report.py \\
      --sector "retail" \\
      --size 150 \\
      --saudi_count 22 \\
      --city "Riyadh"

Requirements:
    ANTHROPIC_API_KEY environment variable must be set.
    pip install anthropic
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("anthropic package not found. Run: pip install anthropic")


SHARED_CONTEXT_PATH = Path(__file__).parent.parent / "modes" / "_shared.md"

SYSTEM_PROMPT = """
أنت محلل متخصص في نظام نطاقات (Nitaqat) وقوانين العمل السعودية.

تعمل كأداة تحليلية مستقلة — ليس مستشاراً قانونياً. أي تحليل تُنتجه يجب أن
يُوضح أنه استرشادي وأن المتطلبات الدقيقة تُتحقق من وزارة الموارد البشرية مباشرةً.

قواعد ثابتة:
- لا تُقدم أرقام نطاقات ثابتة وكأنها نهائية — النظام يتغير
- الحد الأدنى للاحتساب الكامل: 4,000 ريال/شهر + توثيق العقد في قيوة
- الحد الأدنى المقطوع للاحتساب: 1,500 ريال/شهر (احتساب جزئي)
- حُذف النطاق الأصفر في أبريل 2026 — الألوان الآن: بلاتيني، أخضر مرتفع، أخضر متوسط، أخضر منخفض، أحمر
- MRHQs معفاة من النطاقات بالكامل لمدة 10 سنوات
- تضمين حساب نافس إذا كانت هناك فرصة لزيادة السعودة

أنتج المخرج كنص عربي منسق بـ markdown. لا JSON.
"""

ANALYSIS_TEMPLATE = """
حلّل وضع نطاقات المنشأة التالية وأنتج تقريراً منظماً.

=== بيانات المنشأة ===
القطاع: {sector}
عدد الموظفين الكلي: {size}
عدد الموظفين السعوديين الحاليين: {saudi_count}
المدينة: {city}
نسبة السعودة الحالية: {current_pct:.1f}%

=== السياق التنظيمي ===
{shared_context}

=== المخرج المطلوب ===

أنتج تقريراً بالأقسام التالية:

## 1. التصنيف المرجّح
- النطاق المرجّح بناءً على البيانات المتوفرة (مع تحفظ على الدقة)
- الأساس: كيف يؤثر القطاع وحجم المنشأة على متطلبات النطاق؟

## 2. الوضع مقابل الحد الأدنى
- نسبة السعودة الحالية: {current_pct:.1f}%
- النطاق الأدنى المتوقع للقطاع والحجم (تقريبي)
- الفجوة: هل المنشأة فوق الحد أم دونه؟
- عدد السعوديين الإضافيين للوصول للنطاق الأعلى (إذا كانت دون الحد)

## 3. نافس — الفرصة المحتملة
- إذا استبدلت المنشأة موظفاً أجنبياً بسعودي: كم يوفر نافس شهرياً؟
- هل هذا مجدٍ اقتصادياً للمنشأة على المدى القريب؟

## 4. الخطوات التالية
- إجراءان-ثلاثة محددة قابلة للتنفيذ
- كيف يتحقق صاحب المنشأة من وضعه الفعلي (قناة أو منصة)

## 5. تحذير
جملة واحدة تذكّر المستخدم أن هذا التحليل استرشادي لا قانوني.
"""


def load_shared_context() -> str:
    if not SHARED_CONTEXT_PATH.exists():
        return "(ملف _shared.md غير موجود — سيعتمد التحليل على المعرفة العامة)"
    content = SHARED_CONTEXT_PATH.read_text(encoding="utf-8")
    # Keep only Nitaqat and government programs sections to stay within token budget
    sections = content.split("\n## ")
    nitaqat_sections = [s for s in sections if s.startswith(("2.", "3."))]
    if not nitaqat_sections:
        return content[:3000]
    return "\n\n## ".join(nitaqat_sections)[:4000]


def build_prompt(sector: str, size: int, saudi_count: int, city: str) -> str:
    current_pct = (saudi_count / size) * 100 if size > 0 else 0.0
    shared_context = load_shared_context()
    return ANALYSIS_TEMPLATE.format(
        sector=sector,
        size=size,
        saudi_count=saudi_count,
        city=city,
        current_pct=current_pct,
        shared_context=shared_context,
    )


def run_analysis(sector: str, size: int, saudi_count: int, city: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY environment variable not set.")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(sector, size, saudi_count, city)

    print(f"جاري التحليل... ({size} موظف، {saudi_count} سعودي، قطاع: {sector})\n")

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="تقرير تصنيف نطاقات لمنشأة سعودية",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
مثال:
  python3 scripts/nitaqat_report.py --sector retail --size 150 --saudi_count 22 --city Riyadh
        """,
    )
    parser.add_argument(
        "--sector",
        required=True,
        help="قطاع المنشأة (retail, construction, IT, healthcare, ...)",
    )
    parser.add_argument(
        "--size",
        required=True,
        type=int,
        help="عدد الموظفين الكلي",
    )
    parser.add_argument(
        "--saudi_count",
        required=True,
        type=int,
        help="عدد الموظفين السعوديين الحاليين",
    )
    parser.add_argument(
        "--city",
        default="Riyadh",
        help="المدينة الرئيسية للمنشأة (افتراضي: Riyadh)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.size <= 0:
        sys.exit("خطأ: عدد الموظفين يجب أن يكون أكبر من صفر.")
    if args.saudi_count < 0:
        sys.exit("خطأ: عدد السعوديين لا يمكن أن يكون سالباً.")
    if args.saudi_count > args.size:
        sys.exit("خطأ: عدد السعوديين لا يمكن أن يتجاوز إجمالي الموظفين.")

    report = run_analysis(
        sector=args.sector,
        size=args.size,
        saudi_count=args.saudi_count,
        city=args.city,
    )
    print(report)


if __name__ == "__main__":
    main()

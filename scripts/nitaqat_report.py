#!/usr/bin/env python3
"""Generate a Nitaqat eligibility report from a basic cv.md-style text file.

This script is intentionally lightweight and uses only the Python standard library.
It parses a freeform text file for common fields, applies Nitaqat rules from
`modes/نطاق.md`, and prints a structured Arabic report.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

__all__ = [
    "Entity",
    "CandidateInfo",
    "NitaqatCalculator",
    "save_report",
    "run_nitaqat_analysis",
    "generate_nitaqat_report",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Entity:
    name: Optional[str]
    entity_type: Optional[str]
    sector: Optional[str]
    size: Optional[int]


@dataclass
class CandidateInfo:
    nationality: str
    salary: Optional[int]
    qiwa_documented: Optional[bool]
    role_sector: Optional[str]
    experience_level: Optional[str]


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

HIGH_SAUDIZATION_SECTORS = {
    "صيدليات المستشفيات": 65,
    "صيدليات المجتمع": 35,
    "المختبرات الطبية": 70,
    "الأشعة": 65,
    "العلاج الطبيعي": 80,
    "التغذية العلاجية": 80,
    "الهندسة": 30,
    "المحاسبة": 40,
    "التسويق": None,
    "المبيعات": None,
    "السياحة": None,
}

MINIMUM_FULL_CREDIT_SALARY = 4000


class NitaqatCalculator:
    def __init__(self, entity: Entity, candidate: CandidateInfo):
        self.entity = entity
        self.candidate = candidate

    def estimate_nitaqat_class(self) -> str:
        if self.entity.entity_type:
            entity_type = self.entity.entity_type.strip().lower()
            if "rhq" in entity_type or "مقر" in entity_type:
                return "بلاتيني"
            if "sez" in entity_type or "منطقة اقتصادية" in entity_type:
                return "أخضر مرتفع"
            if "pif" in entity_type or "صندوق" in entity_type or "شبه حكومية" in entity_type:
                return "أخضر متوسط"
            if "حكومية" in entity_type:
                return "أخضر متوسط"

        if self.entity.size is not None and self.entity.size < 5:
            return "أخضر مرتفع"

        sector_class = self._sector_based_classification()
        if sector_class:
            return sector_class

        return "غير محدد"

    def _sector_based_classification(self) -> Optional[str]:
        if not self.entity.sector:
            return None

        sector = self.entity.sector.strip().lower()
        if any(keyword in sector for keyword in ("صيدلية", "صيدليات")):
            return "أحمر"
        if any(keyword in sector for keyword in ("طب الأسنان", "أشعة", "مختبر", "علاج طبيعي", "تغذية")):
            return "أحمر"
        if "هندسة" in sector or "محاسبة" in sector:
            return "أخضر منخفض"
        if any(keyword in sector for keyword in ("تسويق", "مبيعات", "سياحة")):
            return "أخضر منخفض"

        return "أخضر متوسط"

    def check_saudization_requirements(self) -> dict[str, Optional[str]]:
        sector = self.candidate.role_sector or self.entity.sector
        if not sector:
            return {
                "requirement": None,
                "note": "القطاع غير معروف، لا يمكن تقدير نسبة السعودة بدقة.",
            }

        sector_key = sector.strip()
        if sector_key in HIGH_SAUDIZATION_SECTORS:
            requirement = HIGH_SAUDIZATION_SECTORS[sector_key]
            if requirement is None:
                return {
                    "requirement": "متصاعدة",
                    "note": "هذا القطاع يخضع لنسب سعودة متصاعدة وقد يتطلب راتب مفاوضة أعلى.",
                }
            if sector_key == "الهندسة":
                return {
                    "requirement": f"{requirement}%",
                    "note": "يشترط راتب SAR 8,000+ واعتماد هيئة المهندسين للاحتساب الكامل.",
                }
            if sector_key == "المحاسبة":
                return {
                    "requirement": f"{requirement}%",
                    "note": "النسبة ترتفع 10% سنوياً حتى 70% بحلول 2028.",
                }
            if sector_key == "طب الأسنان":
                return {
                    "requirement": f"{requirement}%",
                    "note": "يشترط راتب SAR 9,000+ واعتماد هيئة التخصصات.",
                }
            return {
                "requirement": f"{requirement}%",
                "note": None,
            }

        normalized = sector_key.lower()
        if "صيدلية" in normalized:
            return {
                "requirement": "55%",
                "note": "قطاع صيدلة عام يحتاج سعودة متوسطة إلى عالية.",
            }
        if "هندسة" in normalized:
            return {
                "requirement": "30%",
                "note": "الهندسة تتطلب رواتب SAR 8,000+ للاحتساب الكامل في بعض المهن.",
            }

        return {
            "requirement": None,
            "note": "لا توجد قاعدة سعودة محددة لهذا القطاع في البيانات الحالية.",
        }

    def evaluate_impact(self) -> dict[str, str]:
        estimate = self.estimate_nitaqat_class()
        if self.candidate.nationality.lower() == "saudi":
            if estimate in ("بلاتيني", "أخضر مرتفع"):
                return {
                    "impact": "وضع تفاوضي قوي — المنشأة لديها مرونة في توظيف السعوديين.",
                    "recommendation": "تأكد من أن الدور حقيقي ومسؤولياته واضحة قبل التقديم.",
                }
            if estimate == "أحمر":
                return {
                    "impact": "المنشأة قد تواجه ضغط نطاق عالي، لكن الدور قد يظل متاحاً.",
                    "recommendation": "اسأل عن مدى استقرار القسم وخطة الشركة للتوطين في هذا القطاع.",
                }
            return {
                "impact": "الوضع غير محدد تنظيمياً — المعلومات غير كافية.",
                "recommendation": "استعلم مباشرة عن حالة النطاق ووجود عقود سعودية موثقة في قيوة.",
            }

        if self.candidate.nationality.lower() != "saudi":
            if estimate == "أحمر":
                return {
                    "impact": "قد تكون الفرصة مرنة لمقيم، لكن الاستقرار التنظيمي أقل.",
                    "recommendation": "تحقق من سياسة الشركة لتحويل الكفالة ودعم الموظفين الوافدين.",
                }
            if estimate == "بلاتيني":
                return {
                    "impact": "المنشأة تبدو ملتزمة وقد تكون أقل مرونة لتوظيف مقيمين.",
                    "recommendation": "استعلم عن وضع السعودة والقسم إذا كان يتطلب سعوديين حصراً.",
                }
            return {
                "impact": "الوضع غير واضح للوافد — تحتاج بيانات أكثر عن سياسة التوطين للمنشأة.",
                "recommendation": "اطلب معلومات إضافية عن موقف النطاق قبل التقديم.",
            }

        return {
            "impact": "الوضع التنظيمي غير معروف.",
            "recommendation": "تأكد من المعلومات الأساسية حول المنشأة ودورها.",
        }

    def build_warning(self) -> Optional[str]:
        estimate = self.estimate_nitaqat_class()
        senior_levels = {"senior", "lead", "manager", "director", "executive", "كبير", "قيادي", "مدير", "تنفيذي"}
        if estimate not in {"أحمر", "غير محدد"}:
            return None

        high_experience = False
        if self.candidate.experience_level:
            normalized = self.candidate.experience_level.strip().lower()
            if normalized in senior_levels:
                high_experience = True
        if self.candidate.salary is not None and self.candidate.salary >= 25000:
            high_experience = True

        if high_experience:
            return "هذا التقدير يشير إلى منشأة بقيمة خطرة أو غير محددة في نطاق النطاق بينما الدور يبدو يتطلب خبرة عالية. يُنصح بفحص الواقع التنظيمي بدقة قبل التقديم."

        return None

    def generate_report(self) -> str:
        estimate_class = self.estimate_nitaqat_class()
        saudization = self.check_saudization_requirements()
        impact = self.evaluate_impact()

        lines = [
            "# تقرير نطاق Nitaqat",
            "",
            "## Block A — تعريف المنشأة",
            f"اسم المنشأة: {self.entity.name or 'غير متوفر'}",
            f"القطاع / النشاط الاقتصادي: {self.entity.sector or 'غير معروف'}",
            f"نوع المنشأة: {self.entity.entity_type or 'غير محدد'}",
            f"الحجم التقريبي للموظفين: {self.entity.size if self.entity.size is not None else 'غير معروف'}",
            "",
            "## Block B — تقدير النطاق الحالي",
            f"تصنيف النطاق المرجّح: {estimate_class}",
            f"مستوى الثقة في التقدير: {'عالٍ' if self.entity.entity_type or self.entity.sector else 'منخفض — البيانات غير كافية'}",
            f"تحذير قيوة: {'تم توثيق العقد في قيوة.' if self.candidate.qiwa_documented else 'لم يتم توثيق العقد في قيوة أو غير معروف. قد يخفي هذا السعوديين من حساب النطاق.'}",
            "",
            "### تفاصيل سعودة القطاع",
            f"نسبة السعودة المتوقعة: {saudization['requirement'] or 'غير محددة'}",
            f"ملاحظة: {saudization['note'] or 'لا توجد ملاحظات إضافية.'}",
            "",
            "## Block C — تأثير النطاق على المرشح",
            f"الوضع التنظيمي: {impact['impact']}",
            f"توصية: {impact['recommendation']}",
            "",
            "## Block D — الخلاصة والتوصية",
            self._build_recommendation_sentence(estimate_class),
            "",
            "سؤال للمقابلة:",
            "كيف يتعامل القسم مع متطلبات التوطين في هذا النشاط تحديداً؟",
        ]

        warning = self.build_warning()
        if warning:
            lines.insert(lines.index("## Block D — الخلاصة والتوصية"), f"تحذير: {warning}")

        return "\n".join(lines)

    def _build_recommendation_sentence(self, estimate_class: str) -> str:
        if estimate_class in ("بلاتيني", "أخضر مرتفع"):
            return "التوصية: نعم، لا عوائق تنظيمية واضحة في هذا التقدير."
        if estimate_class == "أحمر":
            return "التوصية: نعم مع تحفظات — تحقق من موقف المنشأة واستقرارها."
        if estimate_class == "غير محدد":
            return "التوصية: لا، المعلومات غير كافية لاتخاذ قرار موثوق."
        return "التوصية: نعم مع تحفظات — راجع نسبة السعودة والوثائق قبل التقديم."


def slugify(value: str) -> str:
    safe = re.sub(r"[^\w\-]+", "-", value, flags=re.ASCII)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe.lower() or "report"


def save_report(content: str, entity: Entity) -> Path:
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    name_part = slugify(entity.name or "report")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"nitaqat_report_{name_part}_{timestamp}.md"
    report_path.write_text(content, encoding="utf-8")
    return report_path


def run_nitaqat_analysis(cv_data: Union[str, dict[str, Optional[str]]], entity_data: dict[str, Any]) -> Path:
    """Run the Nitaqat analysis from CV text/data and entity metadata.

    Returns the saved report path.
    """
    if isinstance(cv_data, str):
        parsed = parse_cv_text(cv_data)
    elif isinstance(cv_data, dict):
        parsed = cv_data
    else:
        raise TypeError("cv_data must be text or a dict of parsed fields")

    entity = Entity(
        name=entity_data.get("name") or parsed.get("company_name"),
        entity_type=entity_data.get("entity_type") or parsed.get("entity_type"),
        sector=entity_data.get("sector") or parsed.get("sector"),
        size=entity_data.get("size") or parse_int(parsed.get("employee_count")),
    )
    candidate = CandidateInfo(
        nationality=entity_data.get("nationality", "saudi"),
        salary=entity_data.get("salary") or parse_int(parsed.get("salary")),
        qiwa_documented=entity_data.get("qiwa_documented") if entity_data.get("qiwa_documented") is not None else parse_boolean(parsed.get("qiwa_documented")),
        role_sector=entity_data.get("role_sector") or parsed.get("sector"),
        experience_level=entity_data.get("experience_level") or parsed.get("experience_level"),
    )
    calculator = NitaqatCalculator(entity, candidate)
    report_content = calculator.generate_report()
    return save_report(report_content, entity)

generate_nitaqat_report = run_nitaqat_analysis


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

FIELD_PATTERNS = {
    "company_name": re.compile(r"(?:اسم المنشأة|company name|company|الشركة)\s*[:\-]\s*(.+)", re.I),
    "sector": re.compile(r"(?:القطاع|sector|activity|industry|النشاط)\s*[:\-]\s*(.+)", re.I),
    "entity_type": re.compile(r"(?:نوع المنشأة|entity type|type)\s*[:\-]\s*(.+)", re.I),
    "employee_count": re.compile(r"(?:الحجم|عدد الموظفين|employee_count|employees|size)\s*[:\-]\s*(\d+)", re.I),
    "qiwa_documented": re.compile(r"(?:قيوة|qiwa)\s*[:\-]\s*(yes|no|نعم|لا)", re.I),
    "salary": re.compile(r"(?:راتب|salary)\s*[:\-]\s*(\d{3,7})", re.I),
    "experience_level": re.compile(r"(?:خبرة|experience level|seniority|المستوى)\s*[:\-]\s*(.+)", re.I),
}


def extract_field(text: str, field_name: str) -> Optional[str]:
    pattern = FIELD_PATTERNS[field_name]
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def parse_cv_text(text: str) -> dict[str, Optional[str]]:
    return {
        "company_name": extract_field(text, "company_name"),
        "sector": extract_field(text, "sector"),
        "entity_type": extract_field(text, "entity_type"),
        "employee_count": extract_field(text, "employee_count"),
        "qiwa_documented": extract_field(text, "qiwa_documented"),
        "salary": extract_field(text, "salary"),
        "experience_level": extract_field(text, "experience_level"),
    }


def parse_boolean(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"yes", "نعم", "true", "1"}:
        return True
    if normalized in {"no", "لا", "false", "0"}:
        return False
    return None


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_entity(parsed: dict[str, Optional[str]], args: argparse.Namespace) -> Entity:
    return Entity(
        name=parsed["company_name"] or args.company_name,
        entity_type=parsed["entity_type"] or args.entity_type,
        sector=parsed["sector"] or args.sector,
        size=parse_int(parsed["employee_count"]) or args.employee_count,
    )


def build_candidate(parsed: dict[str, Optional[str]], args: argparse.Namespace) -> CandidateInfo:
    return CandidateInfo(
        nationality=args.nationality,
        salary=parse_int(parsed["salary"]) or args.salary,
        qiwa_documented=parse_boolean(parsed["qiwa_documented"]) if parsed["qiwa_documented"] is not None else args.qiwa_documented,
        role_sector=args.role_sector or args.sector,
        experience_level=parsed["experience_level"] or args.experience_level,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Nitaqat report from cv.md text.")
    parser.add_argument("cv_path", type=Path, help="Path to the cv.md-style input file")
    parser.add_argument("--nationality", choices=["saudi", "resident", "expatriate"], default="saudi", help="Candidate nationality")
    parser.add_argument("--entity-type", help="نوع المنشأة إذا لم يكن موجوداً في النص")
    parser.add_argument("--sector", help="القطاع إذا لم يكن موجوداً في النص")
    parser.add_argument("--company-name", help="اسم المنشأة إذا لم يكن موجوداً في النص")
    parser.add_argument("--employee-count", type=int, help="عدد الموظفين التقريبي")
    parser.add_argument("--qiwa-documented", type=lambda s: s.lower() in ("yes", "نعم", "true", "1"), help="هل العقد موثق في قيوة؟")
    parser.add_argument("--salary", type=int, help="الراتب بالريال السعودي إذا كان معروفاً")
    parser.add_argument("--role-sector", help="قطاع الدور أو المهنة المحددة")
    parser.add_argument("--experience-level", help="مستوى الخبرة أو seniority مثل senior أو manager")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = read_text_file(args.cv_path)
    parsed = parse_cv_text(text)

    entity = build_entity(parsed, args)
    candidate = build_candidate(parsed, args)
    calculator = NitaqatCalculator(entity, candidate)

    report_content = calculator.generate_report()
    report_path = save_report(report_content, entity)

    print(report_content)
    print(f"\nتم حفظ التقرير في: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

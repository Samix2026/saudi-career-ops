"""
Explanation builder for match results.

Takes the list of ComponentScores produced by scorer.py plus the raw candidate
and job data, and assembles the human-readable sections of MatchExplanation:
strongest matches, missing requirements, red flags, concerns, Saudi observations,
and data gaps.

All outputs are factual statements about the data. Nothing is inferred beyond
what the comparison directly shows.
"""

from __future__ import annotations

from ingestion.models.job_posting import EmploymentType, JobPosting, Language, Seniority
from matching.models import (
    CandidateProfile,
    ComponentScore,
    ConfidenceLevel,
    MatchExplanation,
    NationalityStatus,
    SaudiProgramEligibility,
)


_SENIORITY_RANK: dict[Seniority, int] = {
    Seniority.ENTRY: 0,
    Seniority.JUNIOR: 1,
    Seniority.MID: 2,
    Seniority.SENIOR: 3,
    Seniority.LEAD: 4,
    Seniority.MANAGER: 5,
    Seniority.DIRECTOR: 6,
    Seniority.EXECUTIVE: 7,
}

_TAMHEER_TYPICAL_MAX_YEARS = 2.0


def _normalize_skill(s: str) -> str:
    s = s.lower().strip()
    if s.startswith("skill-"):
        s = s[6:]
    return s.replace("-", " ").replace("_", " ")


def build_explanation(
    candidate: CandidateProfile,
    job: JobPosting,
    components: list[ComponentScore],
) -> MatchExplanation:
    return MatchExplanation(
        components=components,
        strongest_matches=_find_strongest_matches(components),
        missing_requirements=_find_missing_requirements(candidate, job),
        red_flags=_find_red_flags(candidate, job),
        concerns=_find_concerns(candidate, job, components),
        saudi_observations=_find_saudi_observations(candidate, job),
        data_gaps=_find_data_gaps(candidate, job, components),
    )


def _find_strongest_matches(components: list[ComponentScore]) -> list[str]:
    return [
        f"{c.factor.replace('_', ' ').title()}: {c.detail}"
        for c in components
        if c.score >= 0.75
    ]


def _find_missing_requirements(
    candidate: CandidateProfile,
    job: JobPosting,
) -> list[str]:
    if not job.skills:
        return []

    candidate_normalized = {_normalize_skill(s) for s in candidate.all_skills}
    missing = [
        f"Skill not found in candidate profile: {skill}"
        for skill in job.skills
        if _normalize_skill(skill) not in candidate_normalized
    ]
    return missing


def _find_red_flags(
    candidate: CandidateProfile,
    job: JobPosting,
) -> list[str]:
    flags = []

    if (
        job.employment_type == EmploymentType.TAMHEER
        and candidate.nationality_status == NationalityStatus.EXPATRIATE
    ):
        flags.append(
            "Tamheer program is restricted to Saudi nationals; candidate is classified as expatriate."
        )

    if (
        job.saudization_signal
        and "only" in job.saudization_signal.lower()
        and candidate.nationality_status == NationalityStatus.EXPATRIATE
    ):
        flags.append(
            f"Job posting explicitly requires Saudi nationals "
            f"({job.saudization_signal!r}); candidate is expatriate."
        )

    if (
        candidate.seniority
        and candidate.seniority != Seniority.UNKNOWN
        and job.seniority
        and job.seniority != Seniority.UNKNOWN
    ):
        c_rank = _SENIORITY_RANK.get(candidate.seniority, -1)
        j_rank = _SENIORITY_RANK.get(job.seniority, -1)
        if c_rank >= 0 and j_rank >= 0 and abs(c_rank - j_rank) >= 3:
            flags.append(
                f"Seniority gap of {abs(c_rank - j_rank)} bands: candidate is "
                f"{candidate.seniority.value}, role targets {job.seniority.value}."
            )

    return flags


def _find_concerns(
    candidate: CandidateProfile,
    job: JobPosting,
    components: list[ComponentScore],
) -> list[str]:
    concerns = []

    loc_comp = next((c for c in components if c.factor == "location"), None)
    if loc_comp and loc_comp.score < 0.3 and not candidate.willing_to_relocate:
        concerns.append(
            "Location preference does not match the job's location and candidate "
            "is not willing to relocate."
        )

    lang_comp = next((c for c in components if c.factor == "language"), None)
    if lang_comp and lang_comp.score < 0.4:
        concerns.append(f"Working language mismatch: {lang_comp.detail}")

    if (
        job.employment_type == EmploymentType.TAMHEER
        and candidate.years_experience is not None
        and candidate.years_experience > _TAMHEER_TYPICAL_MAX_YEARS
    ):
        concerns.append(
            f"Tamheer roles typically target early-career candidates; candidate has "
            f"{candidate.years_experience:.1f} years of experience, which may exceed "
            f"program expectations."
        )

    emp_comp = next((c for c in components if c.factor == "employment_type"), None)
    if emp_comp and emp_comp.score < 0.3:
        concerns.append(f"Employment type mismatch: {emp_comp.detail}")

    sen_comp = next((c for c in components if c.factor == "seniority_alignment"), None)
    if sen_comp and 0.0 < sen_comp.score < 0.6 and sen_comp.confidence == ConfidenceLevel.HIGH:
        concerns.append(f"Seniority: {sen_comp.detail}")

    return concerns


def _find_saudi_observations(
    candidate: CandidateProfile,
    job: JobPosting,
) -> list[str]:
    observations = []

    if job.employment_type == EmploymentType.TAMHEER:
        observations.append(
            "This is a Tamheer (HRDF on-the-job training) role — compensation, contract "
            "terms, and Nitaqat treatment differ from standard employment."
        )

    if job.employment_type == EmploymentType.COOP:
        observations.append(
            "Co-op (تعاون جامعي) role — typically targets enrolled university students; "
            "verify candidate enrollment status."
        )

    if job.saudization_signal:
        observations.append(
            f"Saudization language detected in posting: {job.saudization_signal!r}. "
            f"This may reflect Nitaqat band requirements for the employer."
        )

    if (
        candidate.nationality_status == NationalityStatus.EXPATRIATE
        and job.saudization_signal
    ):
        observations.append(
            "Expatriate candidates can still be hired for Nitaqat-sensitive roles — "
            "the posting signals a preference, not necessarily a hard legal bar, "
            "depending on the employer's current Nitaqat band status."
        )

    if SaudiProgramEligibility.HRDF_SUBSIDY in candidate.saudi_program_eligibility:
        observations.append(
            "Candidate is eligible for HRDF wage subsidy — may reduce effective "
            "hiring cost for private-sector employers."
        )

    if job.language == Language.ARABIC and Language.ARABIC not in candidate.languages:
        observations.append(
            "Job posting is in Arabic; Arabic language proficiency is likely required "
            "for this role."
        )

    return observations


def _find_data_gaps(
    candidate: CandidateProfile,
    job: JobPosting,
    components: list[ComponentScore],
) -> list[str]:
    gaps = []

    for comp in components:
        if comp.confidence != ConfidenceLevel.LOW:
            continue
        if comp.factor == "skill_overlap":
            if not job.skills:
                gaps.append("Job posting: skills/requirements section is absent.")
            if not candidate.all_skills:
                gaps.append("Candidate profile: no skills listed.")
        elif comp.factor == "seniority_alignment":
            if not candidate.seniority or candidate.seniority == Seniority.UNKNOWN:
                gaps.append("Candidate profile: seniority level not stated.")
            if not job.seniority or job.seniority == Seniority.UNKNOWN:
                gaps.append("Job posting: seniority level not specified.")
        elif comp.factor == "location":
            if not candidate.preferred_locations:
                gaps.append("Candidate profile: no preferred locations stated.")
        elif comp.factor == "language":
            if not candidate.languages:
                gaps.append("Candidate profile: working languages not listed.")
        elif comp.factor == "employment_type":
            if not candidate.employment_preferences:
                gaps.append("Candidate profile: employment type preferences not stated.")
            if not job.employment_type or job.employment_type == EmploymentType.UNKNOWN:
                gaps.append("Job posting: employment type not specified.")

    return list(dict.fromkeys(gaps))

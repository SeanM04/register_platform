"""Database-backed completion analysis service."""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db.models import Prefetch

from dashboard.models import AcademicPeriod, CourseResult, Registration

COMPLETION_CACHE_TTL_SECONDS = 300


def _build_completion_cache_key(year, period, faculty):
    parts = [
        f"y={str(year or '').strip()}",
        f"p={str(period or '').strip()}",
        f"f={str(faculty or '').strip()}",
    ]
    return "dashboard:completion:" + "|".join(parts)
from services.completion_rules import (
    get_zero_completion_decision,
    student_completion_percentage,
)


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _safe_rate(numerator: float, denominator: float) -> float:
    """Calculate rate safely with float precision, round only at output."""
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 1)  # Consistent 1 decimal place


def _normalise_gender(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("m"):
        return "male"
    if normalized.startswith("f"):
        return "female"
    return "other"


def _student_name_sort_key(name: str, regnum: str = "") -> tuple[str, str, str]:
    text = " ".join(str(name or "").strip().split())
    if not text:
        return ("", "", str(regnum or "").lower())
    parts = text.split(" ")
    surname = parts[-1].lower()
    given_names = " ".join(parts[:-1]).lower()
    return (surname, given_names, str(regnum or "").lower())


def _extract_period_year(period_name: str) -> str:
    match = re.search(r"(20\d{2})", str(period_name or ""))
    return match.group(1) if match else ""


def _format_period_label(period_name: str) -> str:
    text = str(period_name or "").strip()
    if not text:
        return ""

    year_match = re.search(r"(20\d{2})", text)
    if year_match:
        text = text.replace(year_match.group(1), "").strip()

    text = re.sub(r"\s+", " ", text.replace("-", " - ")).strip(" -")
    return text.title()


def _build_stage_label(registration: Registration) -> str:
    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    if year and semester:
        return f"Year {year}, Semester {semester}"
    if registration.period.academic_year and registration.period.semester:
        return f"Year {registration.period.academic_year}, Semester {registration.period.semester}"
    return registration.period.name


def _display_stage_label(year: int, semester: int) -> str:
    return f"Year {year}, Semester {semester}"


def _progression_period_index(registration: Registration) -> Optional[int]:
    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    if year is None or semester is None or semester <= 0:
        return None
    return ((year - 1) * 2) + semester


def _progression_period_label(registration: Registration) -> str:
    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    if year and semester:
        return f"Y{year} S{semester}"
    return registration.period.name


def _progression_label_from_index(index: int) -> str:
    year = ((index - 1) // 2) + 1
    semester = 1 if index % 2 == 1 else 2
    return f"Y{year} S{semester}"


def _display_decision(decision: str) -> str:
    text = str(decision or "").strip()
    if not text:
        return "Pending"
    return text.title().replace(" And ", " & ")


def _registration_marks(registration: Registration) -> List[float]:
    marks: List[float] = []
    for result in getattr(registration, "prefetched_course_results", []):
        if result.mark is None:
            continue
        marks.append(float(result.mark))
    return marks


def _cohort_period_map() -> tuple[Dict[int, int], List[AcademicPeriod], Dict[int, AcademicPeriod]]:
    periods = list(AcademicPeriod.objects.order_by("external_id", "name"))
    external_ids = [period.external_id for period in periods]
    index_map = {external_id: index for index, external_id in enumerate(external_ids)}
    lookup = {period.external_id: period for period in periods}
    return index_map, periods, lookup


def _cohort_label(period: Optional[AcademicPeriod], fallback: str = "Shifted cohort") -> str:
    if not period:
        return fallback
    return str(period.name or f"Cohort {period.external_id}")


def _get_cohort_sort_index(cohort_label: str) -> int:
    """Extract sort index from cohort label for chronological ordering."""
    # Try to extract year from cohort label like "2023", "2023/2024", etc.
    import re
    year_match = re.search(r"20(\d{2})", str(cohort_label))
    if year_match:
        return int(year_match.group(1))
    
    # Fallback: use hash for consistent ordering
    return hash(str(cohort_label)) % 10000


def _get_all_progression_levels() -> List[tuple[int, str]]:
    """Get all possible progression levels from Y1 S1 to Y5 S2."""
    levels = []
    for year in range(1, 6):  # Y1 to Y5
        for semester in range(1, 3):  # S1 to S2
            # Use same formula as _progression_period_index: ((year - 1) * 2) + semester
            progression_index = ((year - 1) * 2) + semester
            progression_label = f"Y{year} S{semester}"
            levels.append((progression_index, progression_label))
    return levels


def _resolve_effective_cohort(
    original_period: AcademicPeriod,
    shift_offset: int,
    period_index_map: Dict[int, int],
    ordered_periods: List[AcademicPeriod],
) -> tuple[Optional[int], int, str]:
    original_index = period_index_map.get(original_period.external_id, 0)
    target_index = original_index + shift_offset
    if 0 <= target_index < len(ordered_periods):
        target_period = ordered_periods[target_index]
        return target_period.external_id, target_index, _cohort_label(target_period)

    fallback_label = f"{_cohort_label(original_period)} +{shift_offset}"
    return None, target_index, fallback_label


def _zero_completion_reason(
    marks: List[float],
    decision: str,
) -> Optional[str]:
    decision_rule = get_zero_completion_decision(decision)
    if decision_rule:
        return decision_rule.label

    if not marks:
        return "No marks recorded"

    passed_courses = sum(1 for mark in marks if mark >= 50.0)
    failed_courses = len(marks) - passed_courses
    if failed_courses >= 4:
        return "Failed 4+ courses"
    return None


def _build_student_records(
    registrations: List[Registration],
    period_index_map: Dict[int, int],
    ordered_periods: List[AcademicPeriod],
    progression_overrides: Optional[Dict[int, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    ordered_registrations = sorted(
        registrations,
        key=lambda registration: (registration.period.external_id, registration.id),
    )
    if not ordered_registrations:
        return []

    original_registration = ordered_registrations[0]
    original_cohort_label = _cohort_label(original_registration.period)
    original_cohort_external_id = original_registration.period.external_id
    original_cohort_sort_index = period_index_map.get(original_cohort_external_id, 0)
    shift_offset = 0
    records: List[Dict[str, Any]] = []

    for registration in ordered_registrations:
        marks = _registration_marks(registration)
        passed_courses = sum(1 for mark in marks if mark >= 50.0)
        failed_courses = len(marks) - passed_courses
        decision_rule = get_zero_completion_decision(registration.decision)
        completion_rate = student_completion_percentage(marks, decision=registration.decision)
        effective_cohort_external_id, cohort_sort_index, effective_cohort_label = _resolve_effective_cohort(
            original_registration.period,
            shift_offset,
            period_index_map,
            ordered_periods,
        )
        progression_override = (progression_overrides or {}).get(registration.id, {})
        records.append(
            {
                "registration_id": registration.id,
                "regnum": registration.student.registration_number,
                "student_name": registration.student.full_name,
                "programme_id": registration.programme.external_id or registration.programme.id,
                "programme_name": registration.programme.normalized_name,
                "academic_stage": progression_override.get("academic_stage") or _build_stage_label(registration),
                "decision": _display_decision(registration.decision),
                "decision_key": str(registration.decision or "").strip().lower(),
                "completion_rate": completion_rate,
                "zero_completion_reason": _zero_completion_reason(marks, registration.decision),
                "gender_key": _normalise_gender(registration.student.gender),
                "period_external_id": registration.period.external_id,
                "progression_period_index": progression_override.get("progression_period_index", _progression_period_index(registration)),
                "progression_period_label": progression_override.get("progression_period_label") or _progression_period_label(registration),
                "detail_slug": registration.student.registration_number.lower(),
                "effective_cohort_external_id": effective_cohort_external_id,
                "effective_cohort_label": effective_cohort_label,
                "effective_cohort_sort_index": cohort_sort_index,
                "original_cohort_external_id": original_cohort_external_id,
                "original_cohort_label": original_cohort_label,
                "original_cohort_sort_index": original_cohort_sort_index,
                "cumulative_shift": shift_offset,
                "is_shifted": shift_offset > 0,
                "shift_rule_label": decision_rule.label if decision_rule else None,
                "shift_rule_value": decision_rule.shift_semesters if decision_rule else 0,
                "passed_courses": passed_courses,
                "failed_courses": failed_courses,
                "total_courses": len(marks),
            }
        )

        if decision_rule:
            shift_offset += decision_rule.shift_semesters

    return records


def _registration_matches_filters(
    registration: Registration,
    year: Optional[str] = None,
    period: Optional[str] = None,
) -> bool:
    return _period_name_matches_filters(registration.period.name, year=year, period=period)


def _period_name_matches_filters(
    period_name: str,
    year: Optional[str] = None,
    period: Optional[str] = None,
) -> bool:
    if year and _extract_period_year(period_name) != str(year).strip():
        return False

    if period:
        normalized_period = str(period).strip().lower()
        if normalized_period not in {
            str(period_name or "").strip().lower(),
            _format_period_label(period_name).lower(),
        }:
            return False

    return True


def _build_progression_overrides(
    registrations: List[Registration],
    period_index_map: Dict[int, int],
) -> Dict[int, Dict[str, Any]]:
    ordered_registrations = sorted(
        registrations,
        key=lambda registration: (registration.period.external_id, registration.id),
    )
    if not ordered_registrations:
        return {}

    first_registration = ordered_registrations[0]
    first_period_index = period_index_map.get(first_registration.period.external_id)
    if first_period_index is None:
        return {}

    overrides: Dict[int, Dict[str, Any]] = {}
    for registration in ordered_registrations:
        current_period_index = period_index_map.get(registration.period.external_id)
        if current_period_index is None:
            continue
        progression_index = min((current_period_index - first_period_index) + 1, 10)
        display_year = ((progression_index - 1) // 2) + 1
        display_semester = 1 if progression_index % 2 == 1 else 2
        overrides[registration.id] = {
            "progression_period_index": progression_index,
            "progression_period_label": _progression_label_from_index(progression_index),
            "academic_stage": _display_stage_label(display_year, display_semester),
        }
    return overrides


def _get_registration_history(faculty: Optional[str] = None) -> List[Registration]:
    registrations = (
        Registration.objects.select_related(
            "student",
            "programme__department__faculty",
            "period",
            "attendance_type_record",
        )
        .prefetch_related(
            Prefetch(
                "course_results",
                queryset=CourseResult.objects.select_related("course", "attendance_type_record").only(
                    "registration_id",
                    "mark",
                    "attendance_type",
                    "attendance_type_record__name",
                    "course__code",
                    "course__name",
                ),
                to_attr="prefetched_course_results",
            )
        )
        .all()
    )

    if faculty:
        registrations = registrations.filter(programme__department__faculty__name=faculty)

    return list(registrations.order_by("student__registration_number", "period__external_id", "id"))


def _empty_completion_payload() -> Dict[str, Any]:
    return {
        "kpis": {
            "total_students": 0,
            "total_cohorts": 0,
            "average_completion_rate": 0.0,
            "zero_completion_students": 0,
            "shifted_students": 0,
            "gender_distribution": {"male": 0, "female": 0, "other": 0},
        },
        "charts": {
            "cohort_completion": [],
            "programme_completion": [],
            "zero_completion_drivers": [],
        },
        "students": [],
    }


def _build_student_histories(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> List[Dict[str, Any]]:
    registration_history = _get_registration_history(faculty=faculty)
    if not registration_history:
        return []

    period_index_map, ordered_periods, _ = _cohort_period_map()
    registrations_by_student: Dict[str, List[Registration]] = defaultdict(list)
    for registration in registration_history:
        registrations_by_student[registration.student.registration_number].append(registration)

    student_histories: List[Dict[str, Any]] = []
    for student_registrations in registrations_by_student.values():
        ordered_registrations = sorted(
            student_registrations,
            key=lambda registration: (registration.period.external_id, registration.id),
        )
        if not ordered_registrations:
            continue
        original_registration = ordered_registrations[0]

        progression_overrides = _build_progression_overrides(
            ordered_registrations,
            period_index_map,
        )
        student_records = _build_student_records(
            ordered_registrations,
            period_index_map,
            ordered_periods,
            progression_overrides=progression_overrides,
        )
        if not student_records:
            continue

        latest_by_progression: Dict[int, Dict[str, Any]] = {}
        for record, registration in zip(student_records, ordered_registrations):
            record["period_name"] = registration.period.name
            record["period_label"] = _format_period_label(registration.period.name)
            record["faculty_name"] = registration.programme.department.faculty.name
            progression_index = record.get("progression_period_index")
            if progression_index is None:
                continue
            existing = latest_by_progression.get(int(progression_index))
            if existing is None or (
                record["period_external_id"],
                record["registration_id"],
            ) > (
                existing["period_external_id"],
                existing["registration_id"],
            ):
                latest_by_progression[int(progression_index)] = record

        student_histories.append(
            {
                "regnum": original_registration.student.registration_number,
                "original_registration": original_registration,
                "original_cohort_label": student_records[0]["original_cohort_label"],
                "original_cohort_sort_index": student_records[0]["original_cohort_sort_index"],
                "records": student_records,
                "latest_record": max(
                    student_records,
                    key=lambda record: (record["period_external_id"], record["registration_id"]),
                ),
                "latest_by_progression": latest_by_progression,
            }
        )

    return student_histories


def count_students_in_y1s1_august_december_2025() -> Dict[str, Any]:
    """Count students who were in Y1 S1 during August-December 2025 period."""
    from dashboard.models import AcademicPeriod
    
    # Find the August-December 2025 period
    try:
        period_2025 = AcademicPeriod.objects.filter(
            academic_year=2025,
            semester__in=[1, 2]  # Both semesters of 2025
        ).first()
        
        if not period_2025:
            return {"error": "No 2025 academic period found", "count": 0}
            
        # Get registrations for 2025
        registrations = Registration.objects.filter(
            period__academic_year=2025
        ).select_related(
            "student",
            "programme__department__faculty",
            "period",
        ).prefetch_related(
            "course_results"
        )
        
        # Count students in Y1 S1 (progression_index = 1)
        y1s1_count = 0
        y1s1_students = []
        
        for registration in registrations:
            progression_index = _progression_period_index(registration)
            if progression_index == 1:  # Y1 S1
                y1s1_count += 1
                y1s1_students.append({
                    "regnum": registration.student.registration_number,
                    "name": registration.student.full_name,
                    "programme": registration.programme.normalized_name,
                    "period": registration.period.name,
                })
        
        return {
            "period_filter": "August-December 2025",
            "progression_level": "Y1 S1",
            "progression_index": 1,
            "total_students": y1s1_count,
            "students": y1s1_students[:10],  # Show first 10 students
        }
        
    except Exception as e:
        return {"error": str(e), "count": 0}


def get_completion_page_data(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return completion analytics using documented zero-completion and shift rules."""

    student_histories = _build_student_histories(year=year, period=period, faculty=faculty)
    if not student_histories:
        return _empty_completion_payload()

    latest_visible_profiles = []
    for history in student_histories:
        visible_records = [
            record
            for record in history["records"]
            if _period_name_matches_filters(record["period_name"], year=year, period=period)
        ] if (year or period) else history["records"]
        if not visible_records:
            continue
        latest_visible_profiles.append(
            max(
                visible_records,
                key=lambda record: (record["period_external_id"], record["registration_id"]),
            )
        )

    latest_visible_profiles.sort(
        key=lambda row: _student_name_sort_key(row["student_name"], row["regnum"])
    )

    gender_distribution = {"male": 0, "female": 0, "other": 0}
    for profile in latest_visible_profiles:
        gender_distribution[profile["gender_key"]] += 1

    # Use _safe_rate for consistent statistical accuracy
    completion_sum = sum(profile["completion_rate"] for profile in latest_visible_profiles)
    completion_average = round(completion_sum / len(latest_visible_profiles), 1) if latest_visible_profiles else 0.0

    cohort_groups: Dict[tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
    all_cohorts: List[tuple[str, int]] = []
    seen_cohorts = set()
    for history in student_histories:
        for record in history["records"]:
            if year or period:
                if not _period_name_matches_filters(record["period_name"], year=year, period=period):
                    continue
            cohort_label = record["period_name"]
            cohort_sort_index = record["period_external_id"]
            if cohort_label not in seen_cohorts:
                seen_cohorts.add(cohort_label)
                all_cohorts.append((cohort_label, cohort_sort_index))
            progression_index = record.get("progression_period_index")
            if progression_index is None:
                continue
            cohort_groups[(cohort_label, progression_index)].append(record)
    progression_label_map = {
        record["progression_period_index"]: record["progression_period_label"]
        for history in student_histories
        for record in history["records"]
        if record.get("progression_period_index") is not None
        and (not (year or period) or _period_name_matches_filters(record["period_name"], year=year, period=period))
    }
    combined_progression_levels = [
        (index, progression_label_map.get(index, f"P{index}"))
        for index in sorted(progression_label_map.keys())
    ]
    all_cohorts.sort(key=lambda item: item[1])
    cohort_completion = []

    for cohort_label, cohort_sort_index in all_cohorts:
        for progression_index, progression_label in combined_progression_levels:
            profiles = cohort_groups.get((cohort_label, progression_index), [])
            if profiles:
                completion_sum = sum(profile["completion_rate"] for profile in profiles)
                completion_rate = round(completion_sum / len(profiles), 1) if profiles else 0.0
                zero_completion_count = sum(1 for profile in profiles if profile["completion_rate"] == 0.0)
                student_count = len(profiles)
            else:
                completion_rate = None
                zero_completion_count = 0
                student_count = 0
            cohort_completion.append(
                {
                    "effective_cohort_label": cohort_label,
                    "effective_cohort_sort_index": cohort_sort_index,
                    "progression_period": progression_index,
                    "progression_label": progression_label,
                    "completion_rate": completion_rate,
                    "student_count": student_count,
                    "zero_completion_count": zero_completion_count,
                    "pass_share_rate": _safe_rate(student_count - zero_completion_count, student_count),
                }
            )
    cohort_completion.sort(key=lambda row: (row["effective_cohort_sort_index"], row["progression_period"]))

    # Refactor: Use latest_visible_profiles ONLY for consistent aggregation
    programme_groups: Dict[tuple[int, str], List[Dict[str, Any]]] = defaultdict(list)
    for profile in latest_visible_profiles:
        programme_groups[(profile["programme_id"], profile["programme_name"])].append(profile)

    programme_completion = []
    for (programme_id, programme_name), profiles in programme_groups.items():
        zero_completion_count = sum(1 for profile in profiles if profile["completion_rate"] == 0.0)
        
        # Use float precision, round only at final output
        completion_sum = sum(profile["completion_rate"] for profile in profiles)
        completion_rate = round(completion_sum / len(profiles), 1) if profiles else 0.0
        
        programme_completion.append(
            {
                "programme_id": programme_id,
                "programme_name": programme_name,
                "completion_rate": completion_rate,
                "student_count": len(profiles),  # Each student appears exactly once
                "record_count": len(profiles),   # Now matches student_count (no duplication)
                "zero_completion_rate": _safe_rate(zero_completion_count, len(profiles)),
            }
        )
    programme_completion.sort(key=lambda row: row["completion_rate"], reverse=True)

    driver_counts: Dict[str, int] = defaultdict(int)
    for history in student_histories:
        for record in history["records"]:
            if record["completion_rate"] != 0.0:
                continue
            driver_counts[record["zero_completion_reason"] or "Zero completion"] += 1

    zero_completion_drivers = [
        {"label": label, "count": count}
        for label, count in sorted(driver_counts.items(), key=lambda row: (-row[1], row[0]))
    ]

    return {
        "kpis": {
            "total_students": len(latest_visible_profiles),
            "total_cohorts": len(all_cohorts),
            "average_completion_rate": completion_average,
            "zero_completion_students": sum(1 for profile in latest_visible_profiles if profile["completion_rate"] == 0.0),
            "shifted_students": sum(1 for profile in latest_visible_profiles if profile["is_shifted"]),
            "gender_distribution": gender_distribution,
        },
        "charts": {
            "cohort_completion": cohort_completion,
            "programme_completion": programme_completion,
            "zero_completion_drivers": zero_completion_drivers,
        },
        "students": [
            {
                "regnum": profile["regnum"],
                "student_name": profile["student_name"],
                "programme_name": profile["programme_name"],
                "academic_stage": profile["academic_stage"],
                "decision": profile["decision"],
                "effective_cohort": profile["effective_cohort_label"],
                "original_cohort": profile["original_cohort_label"],
                "is_shifted": profile["is_shifted"],
                "zero_completion_reason": profile["zero_completion_reason"],
                "completion_rate": profile["completion_rate"],
                "detail_slug": profile["detail_slug"],
            }
            for profile in latest_visible_profiles
        ],
    }


def get_cached_completion_page_data(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return cached completion analytics, rebuilding only on cold miss or TTL expiry."""

    cache_key = _build_completion_cache_key(year, period, faculty)
    result = cache.get(cache_key)
    if result is None:
        result = get_completion_page_data(year=year, period=period, faculty=faculty)
        cache.set(cache_key, result, COMPLETION_CACHE_TTL_SECONDS)
    return result


def get_completion_fast_kpis(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute headline KPI counts from DB aggregates without building full student histories."""

    qs = Registration.objects.select_related("period")
    if faculty:
        qs = qs.filter(programme__department__faculty__name=faculty)

    if year or period:
        matching_ids = [
            p.external_id
            for p in AcademicPeriod.objects.only("external_id", "name")
            if _period_name_matches_filters(p.name, year=year, period=period)
        ]
        qs = qs.filter(period__external_id__in=matching_ids) if matching_ids else qs.none()

    total_students = qs.values("student_id").distinct().count()
    total_cohorts = qs.values("period__external_id").distinct().count()

    return {
        "kpis": {
            "total_students": total_students,
            "total_cohorts": total_cohorts,
        },
    }


def get_cached_completion_fast_kpis(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return cached fast KPI counts for the current filter scope."""

    cache_key = _build_completion_cache_key(year, period, faculty) + ":fast"
    result = cache.get(cache_key)
    if result is None:
        result = get_completion_fast_kpis(year=year, period=period, faculty=faculty)
        cache.set(cache_key, result, COMPLETION_CACHE_TTL_SECONDS)
    return result


def get_completion_programmes() -> List[Dict[str, Any]]:
    """Return programme options in the shape expected by the completion page."""

    registrations = Registration.objects.select_related("programme").order_by("programme__name")
    seen = set()
    programmes: List[Dict[str, Any]] = []
    for registration in registrations:
        programme = registration.programme
        programme_id = programme.external_id or programme.id
        if programme_id in seen:
            continue
        seen.add(programme_id)
        programmes.append(
            {
                "programme_id": programme_id,
                "programme_name": programme.normalized_name,
            }
        )
    return programmes


def get_completion_faculties() -> List[Dict[str, Any]]:
    """Return faculty options in the shape expected by the completion page."""

    faculty_names = (
        Registration.objects.select_related("programme__department__faculty")
        .values_list("programme__department__faculty__name", flat=True)
        .distinct()
        .order_by("programme__department__faculty__name")
    )
    return [{"faculty": name} for name in faculty_names if name]


def get_completion_academic_years() -> List[Dict[str, Any]]:
    """Return academic year options in the shape expected by the completion page."""

    years = sorted(
        {
            _extract_period_year(period_name)
            for period_name in Registration.objects.select_related("period").values_list("period__name", flat=True)
            if _extract_period_year(period_name)
        }
    )
    return [{"year": year, "label": year, "value": year} for year in years]


def get_completion_periods() -> List[Dict[str, Any]]:
    """Return period options in the shape expected by the completion page."""

    periods = (
        Registration.objects.select_related("period")
        .values_list("period__name", flat=True)
        .distinct()
        .order_by("period__name")
    )
    clean_periods = []
    for period_name in periods:
        display_label = _format_period_label(period_name)
        if display_label:
            clean_periods.append({"period": display_label, "value": display_label})
    return clean_periods


def get_completion_periods_by_year() -> List[Dict[str, Any]]:
    """Return periods grouped by extracted period year for frontend mapping."""

    periods_data = (
        Registration.objects.select_related("period")
        .values_list("period__name", flat=True)
        .distinct()
        .order_by("period__name")
    )

    periods_by_year: Dict[str, Dict[str, Any]] = {}
    for period_name in periods_data:
        year = _extract_period_year(period_name)
        period_label = _format_period_label(period_name)
        if not year or not period_label:
            continue
        if year not in periods_by_year:
            periods_by_year[year] = {"year": year, "value": year, "periods": []}
        periods_by_year[year]["periods"].append({"period": period_label, "value": period_label})

    return [periods_by_year[year] for year in sorted(periods_by_year.keys())]

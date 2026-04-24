"""Database-backed graduation analysis service."""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from dashboard.models import Registration
from services.completion_service import (
    _build_student_records,
    _cohort_period_map,
    _get_registration_history,
    _registration_matches_filters,
)


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _safe_rate(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 0)


def _target_period_from_programme(programme_name: str) -> int:
    normalized = str(programme_name or "").strip().lower()
    if "masters" in normalized or "master" in normalized:
        return 4
    if "engineering" in normalized:
        return 10
    return 8


def _graduation_stage_label(programme_name: str) -> str:
    target_period = _target_period_from_programme(programme_name)
    year = ((target_period - 1) // 2) + 1
    semester = 2 if target_period % 2 == 0 else 1
    return f"{year}.{semester}"


def _graduation_period_label(programme_name: str) -> str:
    target_period = _target_period_from_programme(programme_name)
    year = ((target_period - 1) // 2) + 1
    semester = 2 if target_period % 2 == 0 else 1
    return f"Year {year}, Semester {semester}"


def _decision_indicates_graduation(decision: str) -> bool:
    normalized = str(decision or "").strip().lower()
    return any(term in normalized for term in ("graduat", "complet", "award"))


def _build_completion_lookup(student_histories: List[Dict[str, Any]]) -> Dict[tuple[str, int], float]:
    cohort_period_sequence: Dict[str, Dict[int, int]] = {}
    for history in student_histories:
        for record in history["records"]:
            period_external_id = record.get("period_external_id")
            if period_external_id is None:
                continue
            cohort_label = record["effective_cohort_label"]
            cohort_period_sequence.setdefault(cohort_label, {})
            cohort_period_sequence[cohort_label].setdefault(int(period_external_id), 0)

    for period_sequence in cohort_period_sequence.values():
        for sequence_index, period_external_id in enumerate(sorted(period_sequence), start=1):
            period_sequence[period_external_id] = sequence_index

    grouped_records: Dict[tuple[str, int], List[float]] = defaultdict(list)
    for history in student_histories:
        for record in history["records"]:
            period_external_id = record.get("period_external_id")
            if period_external_id is None:
                continue
            cohort_label = record["effective_cohort_label"]
            relative_progression = cohort_period_sequence.get(cohort_label, {}).get(int(period_external_id))
            if relative_progression is None:
                continue
            grouped_records[(cohort_label, relative_progression)].append(
                float(record.get("completion_rate", 0.0) or 0.0)
            )

    return {
        key: round(sum(values) / len(values))
        for key, values in grouped_records.items()
        if values
    }


def _graduate_rate(effective_cohort_label: str, target_period: int, completion_lookup: Dict[tuple[str, int], float]) -> float:
    completion_values = [
        float(completion_lookup.get((effective_cohort_label, progression_period), 0.0) or 0.0)
        for progression_period in range(1, target_period + 1)
    ]
    if not completion_values:
        return 0.0
    return round(sum(completion_values) / target_period)


def _relative_programme_progression(record: Dict[str, Any], start_progression_period: Optional[int]) -> Optional[int]:
    chronological_progression = record.get("chronological_progression_index")
    if chronological_progression is not None:
        return int(chronological_progression)

    progression_period = record.get("progression_period_index")
    if progression_period is None or start_progression_period is None:
        return None
    return int(progression_period) - int(start_progression_period) + 1


def _is_graduated_record(record: Dict[str, Any], target_period: int, start_progression_period: Optional[int]) -> bool:
    progression_period = _relative_programme_progression(record, start_progression_period)
    if progression_period is not None and progression_period >= target_period:
        return True
    return _decision_indicates_graduation(record.get("decision_key", ""))


def _build_student_histories(faculty: Optional[str] = None) -> List[Dict[str, Any]]:
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
        student_records = _build_student_records(ordered_registrations, period_index_map, ordered_periods)
        if not student_records:
            continue
        start_progression_period = student_records[0].get("progression_period_index")

        for chronological_index, (record, registration) in enumerate(
            zip(student_records, ordered_registrations),
            start=1,
        ):
            record["faculty_name"] = registration.programme.department.faculty.name
            record["period_name"] = registration.period.name
            record["period_year"] = registration.period.academic_year
            record["period_semester"] = registration.period.semester
            record["chronological_progression_index"] = chronological_index
            record["relative_programme_progression_index"] = _relative_programme_progression(
                record,
                start_progression_period,
            )

        student_histories.append(
            {
                "regnum": ordered_registrations[0].student.registration_number,
                "records": student_records,
                "registrations": ordered_registrations,
                "start_progression_period": start_progression_period,
                "latest_record": max(
                    student_records,
                    key=lambda record: (record["period_external_id"], record["registration_id"]),
                ),
            }
        )

    return student_histories


def _empty_graduation_payload() -> Dict[str, Any]:
    return {
        "kpis": {
            "total_graduated_students": 0,
            "average_graduation_rate": 0.0,
            "on_time_graduation_rate": 0.0,
            "best_faculty_rate": 0.0,
            "best_faculty_name": "",
            "graduation_rate_by_faculty": {},
        },
        "charts": {
            "programme_graduation_rate": [],
            "cohort_graduation_rate": [],
            "faculty_graduation_rate": [],
            "graduation_timing": [],
            "readiness_programmes": [],
            "readiness_cohorts": [],
        },
        "meta": {
            "has_graduates": False,
            "snapshot_message": "No graduation data is available for the current filters.",
            "graduation_like_decision_count": 0,
            "students_one_step_from_target": 0,
            "students_within_two_steps": 0,
            "readiness_population": 0,
        },
        "students": [],
    }


def _steps_remaining(record: Dict[str, Any], target_period: int) -> Optional[int]:
    relative_progression = record.get("relative_programme_progression_index")
    if relative_progression is None:
        return None
    return int(target_period) - int(relative_progression)


def get_graduation_page_data(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return graduation analytics aligned with the documented cohort-based graduation rules."""

    student_histories = _build_student_histories(faculty=faculty)
    if not student_histories:
        return _empty_graduation_payload()

    completion_lookup = _build_completion_lookup(student_histories)
    original_cohort_enrollment: Dict[str, set[str]] = defaultdict(set)
    faculty_population: Dict[str, set[str]] = defaultdict(set)
    cohort_sort_indexes: Dict[str, int] = {}
    for history in student_histories:
        first_record = history["records"][0]
        latest_record = history["latest_record"]
        original_cohort_enrollment[first_record["original_cohort_label"]].add(history["regnum"])
        faculty_population[latest_record["faculty_name"]].add(history["regnum"])
        for record in history["records"]:
            cohort_sort_indexes.setdefault(
                record["effective_cohort_label"],
                int(record.get("effective_cohort_sort_index", 0) or 0),
            )

    latest_visible_profiles: List[Dict[str, Any]] = []
    graduated_students: List[Dict[str, Any]] = []
    for history in student_histories:
        visible_records = [
            record
            for record, registration in zip(history["records"], history["registrations"])
            if _registration_matches_filters(registration, year=year, period=period)
        ]
        if not visible_records:
            continue

        latest_visible = max(
            visible_records,
            key=lambda record: (record["period_external_id"], record["registration_id"]),
        )
        target_period = _target_period_from_programme(latest_visible["programme_name"])
        steps_remaining = _steps_remaining(latest_visible, target_period)
        is_graduated = _is_graduated_record(latest_visible, target_period, history.get("start_progression_period"))
        latest_visible_profiles.append(
            {
                "history": history,
                "record": latest_visible,
                "target_period": target_period,
                "steps_remaining": steps_remaining,
                "is_graduated": is_graduated,
            }
        )

        if not is_graduated:
            continue

        effective_cohort_label = latest_visible["effective_cohort_label"]
        original_cohort_label = latest_visible["original_cohort_label"]
        graduation_rate = _graduate_rate(effective_cohort_label, target_period, completion_lookup)
        graduated_students.append(
            {
                "regnum": latest_visible["regnum"],
                "student_name": latest_visible["student_name"],
                "programme_id": latest_visible["programme_id"],
                "programme_name": latest_visible["programme_name"],
                "faculty": latest_visible["faculty_name"],
                "graduation_rate": graduation_rate,
                "graduation_stage": _graduation_stage_label(latest_visible["programme_name"]),
                "graduation_period_label": _graduation_period_label(latest_visible["programme_name"]),
                "target_period": target_period,
                "effective_cohort": effective_cohort_label,
                "original_cohort": original_cohort_label,
                "on_time": effective_cohort_label == original_cohort_label,
                "period_external_id": latest_visible["period_external_id"],
            }
        )

    graduated_students.sort(key=lambda row: (row["student_name"], row["regnum"]))
    if not latest_visible_profiles:
        return _empty_graduation_payload()

    readiness_profiles = [
        profile
        for profile in latest_visible_profiles
        if not profile["is_graduated"] and profile["steps_remaining"] is not None and profile["steps_remaining"] > 0
    ]
    one_step_profiles = [profile for profile in readiness_profiles if profile["steps_remaining"] == 1]
    within_two_profiles = [profile for profile in readiness_profiles if profile["steps_remaining"] <= 2]
    graduation_like_decision_count = sum(
        1
        for profile in latest_visible_profiles
        if _decision_indicates_graduation(profile["record"].get("decision_key", ""))
    )

    readiness_programme_groups: Dict[tuple[int, str], List[Dict[str, Any]]] = defaultdict(list)
    readiness_cohort_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for profile in one_step_profiles:
        record = profile["record"]
        readiness_programme_groups[(record["programme_id"], record["programme_name"])].append(profile)
        readiness_cohort_groups[record["effective_cohort_label"]].append(profile)

    readiness_programmes = [
        {
            "programme_id": programme_id,
            "programme_name": programme_name,
            "student_count": len(profiles),
            "closest_remaining_steps": min(int(profile["steps_remaining"]) for profile in profiles),
        }
        for (programme_id, programme_name), profiles in readiness_programme_groups.items()
    ]
    readiness_programmes.sort(
        key=lambda row: (-row["student_count"], row["closest_remaining_steps"], row["programme_name"])
    )

    readiness_cohorts = [
        {
            "effective_cohort_label": cohort_label,
            "effective_cohort_sort_index": cohort_sort_indexes.get(cohort_label, 0),
            "student_count": len(profiles),
            "closest_remaining_steps": min(int(profile["steps_remaining"]) for profile in profiles),
        }
        for cohort_label, profiles in readiness_cohort_groups.items()
    ]
    readiness_cohorts.sort(
        key=lambda row: (row["effective_cohort_sort_index"], -row["student_count"], row["effective_cohort_label"])
    )

    snapshot_message = ""
    if not graduated_students:
        snapshot_message = (
            f"No visible students currently meet the documented graduation rule. "
            f"{len(one_step_profiles)} students are one step from target, "
            f"{len(within_two_profiles)} are within two steps, and the snapshot contains "
            f"{graduation_like_decision_count} graduation-like decisions."
        )

    total_graduated_students = len(graduated_students)
    average_graduation_rate = round(
        sum(student["graduation_rate"] for student in graduated_students) / total_graduated_students,
        0,
    ) if total_graduated_students else 0.0
    on_time_graduation_rate = _safe_rate(
        sum(1 for student in graduated_students if student["on_time"]),
        total_graduated_students,
    )

    faculty_graduated: Dict[str, int] = defaultdict(int)
    programme_rates: Dict[tuple[int, str], List[float]] = defaultdict(list)
    cohort_graduated: Dict[str, int] = defaultdict(int)
    timing_counts = {"On-time": 0, "Delayed": 0}

    for student in graduated_students:
        faculty_graduated[student["faculty"]] += 1
        programme_rates[(student["programme_id"], student["programme_name"])].append(student["graduation_rate"])
        cohort_graduated[student["effective_cohort"]] += 1
        timing_counts["On-time" if student["on_time"] else "Delayed"] += 1

    graduation_rate_by_faculty = {
        faculty_name: _safe_rate(faculty_graduated.get(faculty_name, 0), len(student_numbers))
        for faculty_name, student_numbers in faculty_population.items()
    }
    best_faculty_name = ""
    best_faculty_rate = 0.0
    if total_graduated_students and graduation_rate_by_faculty:
        best_faculty_name, best_faculty_rate = max(
            graduation_rate_by_faculty.items(),
            key=lambda item: item[1],
        )

    programme_graduation_rate = [
        {
            "programme_id": programme_id,
            "programme_name": programme_name,
            "graduation_rate": round(sum(rates) / len(rates), 0),
            "graduated_count": len(rates),
        }
        for (programme_id, programme_name), rates in programme_rates.items()
        if rates
    ]
    programme_graduation_rate.sort(key=lambda row: row["graduation_rate"], reverse=True)

    cohort_graduation_rate = [
        {
            "effective_cohort_label": cohort_label,
            "effective_cohort_sort_index": cohort_sort_indexes.get(cohort_label, 0),
            "graduated_count": graduated_count,
            "enrolled_count": len(original_cohort_enrollment.get(cohort_label, set())),
            "graduation_rate": _safe_rate(
                graduated_count,
                len(original_cohort_enrollment.get(cohort_label, set())),
            ),
        }
        for cohort_label, graduated_count in sorted(
            cohort_graduated.items(),
            key=lambda item: (
                cohort_sort_indexes.get(item[0], 0),
                item[0],
            ),
        )
    ]

    faculty_graduation_rate = [
        {
            "faculty": faculty_name,
            "graduation_rate": round(rate, 0),
            "graduated_count": faculty_graduated.get(faculty_name, 0),
            "enrolled_count": len(faculty_population.get(faculty_name, set())),
        }
        for faculty_name, rate in sorted(
            graduation_rate_by_faculty.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    graduation_timing = [
        {"label": label, "count": count}
        for label, count in timing_counts.items()
        if count
    ]
    return {
        "kpis": {
            "total_graduated_students": total_graduated_students,
            "average_graduation_rate": average_graduation_rate,
            "on_time_graduation_rate": on_time_graduation_rate,
            "best_faculty_rate": round(best_faculty_rate, 0),
            "best_faculty_name": best_faculty_name,
            "graduation_rate_by_faculty": graduation_rate_by_faculty,
        },
        "charts": {
            "programme_graduation_rate": programme_graduation_rate,
            "cohort_graduation_rate": cohort_graduation_rate,
            "faculty_graduation_rate": faculty_graduation_rate,
            "graduation_timing": graduation_timing,
            "readiness_programmes": readiness_programmes,
            "readiness_cohorts": readiness_cohorts,
        },
        "meta": {
            "has_graduates": bool(graduated_students),
            "snapshot_message": snapshot_message,
            "graduation_like_decision_count": graduation_like_decision_count,
            "students_one_step_from_target": len(one_step_profiles),
            "students_within_two_steps": len(within_two_profiles),
            "readiness_population": len(readiness_profiles),
        },
        "students": [
            {
                "regnum": student["regnum"],
                "student_name": student["student_name"],
                "programme_name": student["programme_name"],
                "faculty": student["faculty"],
                "graduation_rate": student["graduation_rate"],
                "graduation_stage": student["graduation_stage"],
                "graduation_period_label": student["graduation_period_label"],
                "effective_cohort": student["effective_cohort"],
                "original_cohort": student["original_cohort"],
                "on_time": student["on_time"],
            }
            for student in graduated_students
        ],
    }


def get_graduation_programmes() -> List[Dict[str, Any]]:
    """Return programme options in the shape expected by the graduation page."""

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


def get_graduation_faculties() -> List[Dict[str, Any]]:
    """Return faculty options in the shape expected by the graduation page."""

    faculty_names = (
        Registration.objects.select_related("programme__department__faculty")
        .values_list("programme__department__faculty__name", flat=True)
        .distinct()
        .order_by("programme__department__faculty__name")
    )
    return [{"faculty": name} for name in faculty_names if name]

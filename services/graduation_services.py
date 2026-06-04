"""Database-backed graduation analysis service."""

from collections import defaultdict
import logging
from typing import Any, Dict, List, Optional

from django.core.cache import cache

from dashboard.models import Registration
from dashboard.student_history import (
    _programme_is_engineering,
    build_student_timeline,
    extract_registration_year_semester,
)
from services.completion_service import (
    _build_student_records,
    _cohort_period_map,
    _get_registration_history,
    _registration_matches_filters,
)

logger = logging.getLogger(__name__)


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _safe_rate(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 0)


def _student_name_sort_key(name: str, regnum: str = "") -> tuple[str, str, str]:
    text = " ".join(str(name or "").strip().split())
    if not text:
        return ("", "", str(regnum or "").lower())
    parts = text.split(" ")
    surname = parts[-1].lower()
    given_names = " ".join(parts[:-1]).lower()
    return (surname, given_names, str(regnum or "").lower())


def _target_period_from_programme(programme_name: str, student_regnum: str = None) -> int:
    # Check cache first
    cache_key = (str(programme_name or ""), student_regnum)
    if cache_key in _target_period_cache:
        return _target_period_cache[cache_key]
    
    normalized = str(programme_name or "").strip().lower()
    
    if "masters" in normalized or "master" in normalized or "msc" in normalized:
        result = 3
    elif "eng" in normalized:
        # For engineering students, check attendance type from course results to distinguish visiting vs conventional
        if student_regnum:
            attendance_type = _get_student_attendance_type(student_regnum)
            
            if attendance_type and "visiting" in str(attendance_type).lower():
                result = 8
            else:
                result = 10
        else:
            # Fallback to programme name checking if no student regnum provided
            if "visiting" in normalized or "exchange" in normalized or "short" in normalized:
                result = 8
            else:
                result = 10
    else:
        # For all other programmes (4-year programmes), check attendance type to distinguish visiting vs conventional
        if student_regnum:
            attendance_type = _get_student_attendance_type(student_regnum)
            
            if attendance_type and "visiting" in str(attendance_type).lower():
                result = 6
            else:
                result = 8
        else:
            # Fallback to programme name checking if no student regnum provided
            if "visiting" in normalized or "exchange" in normalized or "short" in normalized:
                result = 6
            else:
                result = 8
    
    # Cache the result
    logger.debug(
        "graduation.target_period programme=%s regnum=%s engineering=%s attendance_type=%s target_period=%s",
        programme_name,
        student_regnum,
        _programme_is_engineering(programme_name),
        _get_student_attendance_type(student_regnum) if student_regnum else "",
        result,
    )
    _target_period_cache[cache_key] = result
    return result


# Cache for attendance types to avoid repeated database queries
_attendance_type_cache: Dict[str, Optional[str]] = {}

# Cache for target periods and graduation stages
_target_period_cache: Dict[tuple[str, Optional[str]], int] = {}
_graduation_stage_cache: Dict[tuple[str, Optional[str]], str] = {}
_graduation_period_cache: Dict[tuple[str, Optional[str]], str] = {}

def _normalized_attendance_text(value: Any) -> str:
    """Return a trimmed attendance-type label."""

    return str(value or "").strip()


def _resolve_registration_attendance_type(registration: Registration) -> Optional[str]:
    """Resolve the strongest attendance-type label from a registration and its results."""

    registration_type = _normalized_attendance_text(
        getattr(getattr(registration, "attendance_type_record", None), "name", "")
    )
    if registration_type:
        return registration_type

    prefetched_results = getattr(registration, "prefetched_course_results", None)
    if prefetched_results is not None:
        results = list(prefetched_results)
    else:
        results = list(registration.course_results.select_related("attendance_type_record").all())

    for result in results:
        result_type = _normalized_attendance_text(
            getattr(getattr(result, "attendance_type_record", None), "name", "")
        ) or _normalized_attendance_text(getattr(result, "attendance_type", ""))
        if result_type:
            return result_type

    return None


def _batch_get_attendance_types(student_regnums: List[str]) -> Dict[str, Optional[str]]:
    """Batch fetch attendance types for multiple students to reduce database queries."""
    try:
        # Filter out already cached regnums
        uncached_regnums = [regnum for regnum in student_regnums if regnum not in _attendance_type_cache]
        if not uncached_regnums:
            return _attendance_type_cache
        
        # Get all registrations for uncached students in one query
        registrations = Registration.objects.filter(
            student__registration_number__in=uncached_regnums
        ).select_related(
            "student",
            "attendance_type_record",
        ).prefetch_related(
            "course_results__attendance_type_record",
        ).order_by('student__registration_number', '-period__external_id', '-id')

        resolved_regnums = set()
        for reg in registrations:
            regnum = reg.student.registration_number
            if regnum in resolved_regnums:
                continue
            attendance_type = _resolve_registration_attendance_type(reg)
            if attendance_type:
                _attendance_type_cache[regnum] = attendance_type
                resolved_regnums.add(regnum)

        for regnum in uncached_regnums:
            if regnum not in _attendance_type_cache:
                _attendance_type_cache[regnum] = None
        
        return _attendance_type_cache
    except Exception:
        # Fallback: set all to None if batch query fails
        for regnum in student_regnums:
            _attendance_type_cache[regnum] = None
        return _attendance_type_cache

def _get_student_attendance_type(student_regnum: str) -> Optional[str]:
    """Get attendance type from student's course results to distinguish visiting vs conventional."""
    # Check cache first
    if student_regnum in _attendance_type_cache:
        return _attendance_type_cache[student_regnum]
    
    # If not in cache, this will be handled by batch loading
    return None


def _graduation_stage_label(programme_name: str, student_regnum: str = None) -> str:
    # Check cache first
    cache_key = (str(programme_name or ""), student_regnum)
    if cache_key in _graduation_stage_cache:
        return _graduation_stage_cache[cache_key]
    
    target_period = _target_period_from_programme(programme_name, student_regnum)
    
    # Special handling for masters: 3 semesters = 2.1 (Year 2, Semester 1)
    if "masters" in str(programme_name or "").strip().lower() or "master" in str(programme_name or "").strip().lower() or "msc" in str(programme_name or "").strip().lower():
        year = 2
        semester = 1
        stage_label = f"{year}.{semester}"
    else:
        year = ((target_period - 1) // 2) + 1
        semester = 2 if target_period % 2 == 0 else 1
        stage_label = f"{year}.{semester}"
    
    # Cache the result
    _graduation_stage_cache[cache_key] = stage_label
    return stage_label


def _graduation_period_label(programme_name: str, student_regnum: str = None) -> str:
    # Check cache first
    cache_key = (str(programme_name or ""), student_regnum)
    if cache_key in _graduation_period_cache:
        return _graduation_period_cache[cache_key]
    
    target_period = _target_period_from_programme(programme_name, student_regnum)
    
    # Special handling for masters: 3 semesters = Year 2, Semester 1
    if "masters" in str(programme_name or "").strip().lower() or "master" in str(programme_name or "").strip().lower() or "msc" in str(programme_name or "").strip().lower():
        year = 2
        semester = 1
        period_label = f"Year {year}, Semester {semester}"
    else:
        # For non-masters programmes, use the target period to calculate year and semester
        # This automatically handles visiting vs conventional students correctly
        year = ((target_period - 1) // 2) + 1
        semester = 2 if target_period % 2 == 0 else 1
        period_label = f"Year {year}, Semester {semester}"
    
    # Cache the result
    _graduation_period_cache[cache_key] = period_label
    return period_label


def _decision_indicates_graduation(decision: str) -> bool:
    normalized = str(decision or "").strip().lower()
    return any(term in normalized for term in (
        "graduat",
        "complet",
        "award",
        "pending",
        "proceed",
        "senate",
        "dissertation complete",
        "thesis complete",
        "resubmit dissertation within 3 months",
    ))


def _iter_registration_results(registration: Registration) -> List[Any]:
    prefetched_results = getattr(registration, "prefetched_course_results", None)
    if prefetched_results is not None:
        return list(prefetched_results)
    return list(registration.course_results.select_related("course").all())


def _result_mark_value(result: Any) -> Optional[float]:
    mark = getattr(result, "mark", None)
    if mark is None:
        return None
    return float(mark)


def _course_text(result: Any) -> str:
    course = getattr(result, "course", None)
    code = str(getattr(course, "code", "") or "").strip()
    name = str(getattr(course, "name", "") or "").strip()
    return f"{code} {name}".strip().lower()


def _build_academic_completion_state(
    visible_registrations: List[Registration],
    latest_record: Dict[str, Any],
) -> Dict[str, Any]:
    latest_attempt_by_course: Dict[str, Any] = {}
    dissertation_completed = True
    internship_completed = True

    for registration in visible_registrations:
        for result in _iter_registration_results(registration):
            course = getattr(result, "course", None)
            course_key = str(getattr(course, "code", "") or "").strip() or f"COURSE-{getattr(result, 'id', '')}"
            latest_attempt_by_course[course_key] = result

    earned_credits = 0
    required_credits = 0
    failed_modules_remaining = 0

    for result in latest_attempt_by_course.values():
        required_credits += 1
        mark_value = _result_mark_value(result)
        if mark_value is not None and mark_value >= 50:
            earned_credits += 1
        else:
            failed_modules_remaining += 1

        course_text = _course_text(result)
        if any(keyword in course_text for keyword in ("dissertation", "thesis")):
            dissertation_completed = mark_value is not None and mark_value >= 50 and dissertation_completed
        if any(keyword in course_text for keyword in ("internship", "attachment")):
            internship_completed = mark_value is not None and mark_value >= 50 and internship_completed

    latest_decision = str(latest_record.get("decision_key", "") or "").strip().lower()
    has_unresolved_suspension = "suspend" in latest_decision
    has_unresolved_exclusion = any(term in latest_decision for term in ("exclude", "expel", "discontinue"))
    academically_excluded = has_unresolved_suspension or has_unresolved_exclusion
    latest_failed_courses = int(latest_record.get("failed_courses", 0) or 0)
    latest_carrying = int(latest_record.get("carrying", 0) or 0)

    failed_modules_remaining = max(
        failed_modules_remaining,
        latest_failed_courses,
        latest_carrying,
    )

    academic_requirements_completed = (
        failed_modules_remaining == 0
        and not academically_excluded
        and dissertation_completed
        and internship_completed
    )

    return {
        "academic_requirements_completed": academic_requirements_completed,
        "earned_credits": earned_credits,
        "required_credits": required_credits,
        "failed_modules_remaining": failed_modules_remaining,
        "dissertation_completed": dissertation_completed,
        "internship_completed": internship_completed,
        "has_unresolved_suspension": has_unresolved_suspension,
        "has_unresolved_exclusion": has_unresolved_exclusion,
        "academically_excluded": academically_excluded,
    }


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


def _is_graduation_eligible(
    record: Dict[str, Any],
    target_period: int,
    academic_state: Optional[Dict[str, Any]] = None,
) -> bool:
    """Return whether the visible record has reached the documented graduation-eligibility stage."""

    chronological_progression = record.get("chronological_progression_index")
    if chronological_progression is None:
        return False
    state = academic_state or {}
    academic_requirements_completed = bool(state.get("academic_requirements_completed", True))
    earned_credits = int(state.get("earned_credits", 0) or 0)
    required_credits = int(state.get("required_credits", 0) or 0)
    failed_modules_remaining = int(state.get("failed_modules_remaining", 0) or 0)
    academically_excluded = bool(state.get("academically_excluded", False))
    return (
        int(chronological_progression) >= int(target_period)
        and academic_requirements_completed
        and earned_credits >= required_credits
        and failed_modules_remaining == 0
        and not academically_excluded
    )


def _relative_programme_progression(record: Dict[str, Any], start_progression_period: Optional[int]) -> Optional[int]:
    chronological_progression = record.get("chronological_progression_index")
    if chronological_progression is not None:
        return int(chronological_progression)

    progression_period = record.get("progression_period_index")
    if progression_period is None or start_progression_period is None:
        return None
    return int(progression_period) - int(start_progression_period) + 1


def _is_graduated_record(
    record: Dict[str, Any],
    target_period: int,
    start_progression_period: Optional[int],
    academic_state: Optional[Dict[str, Any]] = None,
) -> bool:
    decision_key = record.get("decision_key", "")
    return _is_graduation_eligible(record, target_period, academic_state) and _decision_indicates_graduation(decision_key)


def _graduation_display_stage(
    record: Dict[str, Any],
    programme_name: str,
    student_regnum: str,
    is_eligible: bool,
) -> str:
    """Return the graduation page stage label for a visible student profile."""

    if is_eligible:
        return _graduation_period_label(programme_name, student_regnum)
    return record.get("academic_level_label") or ""


def _classify_graduation_status(
    record: Dict[str, Any],
    target_period: int,
    academic_state: Dict[str, Any],
    is_eligible: bool,
    is_graduated: bool,
    steps_remaining: Optional[int],
) -> str:
    if is_graduated:
        return "graduated"
    if is_eligible:
        return "eligible"
    if steps_remaining == 1:
        return "near_eligible"
    if steps_remaining is not None and steps_remaining < 0:
        return "delayed"
    if (
        int(academic_state.get("failed_modules_remaining", 0) or 0) > 0
        or bool(academic_state.get("academically_excluded"))
        or float(record.get("completion_rate", 0.0) or 0.0) < 50.0
    ):
        return "at_risk"
    return "active"


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
        timeline = build_student_timeline(ordered_registrations)
        registration_level_index = {}
        for group in timeline["groups"]:
            level_meta = {
                "display_year": group["year"],
                "display_semester": group["semester"],
                "academic_level_label": group["academic_level_label"],
            }
            for registration in group["registrations"]:
                registration_level_index[registration.id] = level_meta
        student_records = _build_student_records(ordered_registrations, period_index_map, ordered_periods)
        if not student_records:
            continue
        start_progression_period = student_records[0].get("progression_period_index")

        for chronological_index, (record, registration) in enumerate(
            zip(student_records, ordered_registrations),
            start=1,
        ):
            department = registration.programme.department if registration.programme else None
            level_meta = registration_level_index.get(registration.id)
            if level_meta:
                display_year = level_meta["display_year"]
                display_semester = level_meta["display_semester"]
                academic_level_label = level_meta["academic_level_label"]
            else:
                display_year, display_semester = extract_registration_year_semester(registration)
                academic_level_label = f"Year {display_year} Semester {display_semester}"
            record["faculty_name"] = registration.programme.department.faculty.name
            record["department_name"] = department.name if department else "Unknown"
            record["period_name"] = registration.period.name
            record["period_year"] = display_year
            record["period_semester"] = display_semester
            record["academic_level_label"] = academic_level_label
            record["chronological_progression_index"] = chronological_index
            record["carrying"] = int(getattr(registration, "carrying", 0) or 0)
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
            "eligible_students_count": 0,
            "non_eligible_students_count": 0,
            "graduated_students_count": 0,
            "official_graduated_count": 0,
            "on_time_graduates": 0,
            "delayed_graduates": 0,
            "near_eligible_students_count": 0,
            "delayed_students_count": 0,
            "active_students_count": 0,
            "at_risk_students_count": 0,
            "faculty_eligible_students": {},
            "programme_eligible_students": {},
        },
        "students": [],
    }


def _steps_remaining(record: Dict[str, Any], target_period: int) -> Optional[int]:
    relative_progression = record.get("relative_programme_progression_index")
    if relative_progression is None:
        return None
    return int(target_period) - int(relative_progression)


def _clear_graduation_caches() -> None:
    """Clear all graduation-related caches to free memory."""
    global _attendance_type_cache, _target_period_cache, _graduation_stage_cache, _graduation_period_cache
    _attendance_type_cache.clear()
    _target_period_cache.clear()
    _graduation_stage_cache.clear()
    _graduation_period_cache.clear()


def get_graduation_page_data(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return graduation analytics aligned with the documented cohort-based graduation rules."""
    
    # Clear caches at the start of each request to ensure fresh data
    _clear_graduation_caches()
    
    student_histories = _build_student_histories(faculty=faculty)
    
    if not student_histories:
        return _empty_graduation_payload()
    
    # Pre-load all attendance types in batch for performance
    all_student_regnums = list(set(
        history["regnum"] for history in student_histories
    ))
    _batch_get_attendance_types(all_student_regnums)

    completion_lookup = _build_completion_lookup(student_histories)
    cohort_sort_indexes: Dict[str, int] = {}
    for history in student_histories:
        for record in history["records"]:
            cohort_sort_indexes.setdefault(
                record["effective_cohort_label"],
                int(record.get("effective_cohort_sort_index", 0) or 0),
            )

    latest_visible_profiles: List[Dict[str, Any]] = []
    graduated_students: List[Dict[str, Any]] = []
    for history in student_histories:
        visible_pairs = [
            (record, registration)
            for record, registration in zip(history["records"], history["registrations"])
            if _registration_matches_filters(registration, year=year, period=period)
        ]
        visible_records = [record for record, _ in visible_pairs]
        if not visible_records:
            continue
        visible_registrations = [registration for _, registration in visible_pairs]

        latest_visible = max(
            visible_records,
            key=lambda record: (record["period_external_id"], record["registration_id"]),
        )
        target_period = _target_period_from_programme(latest_visible["programme_name"], latest_visible["regnum"])
        academic_state = _build_academic_completion_state(visible_registrations, latest_visible)
        is_eligible = _is_graduation_eligible(latest_visible, target_period, academic_state)
        steps_remaining = _steps_remaining(latest_visible, target_period)
        is_graduated = _is_graduated_record(
            latest_visible,
            target_period,
            history.get("start_progression_period"),
            academic_state,
        )
        graduation_stage_label = _graduation_display_stage(
            latest_visible,
            latest_visible["programme_name"],
            latest_visible["regnum"],
            is_eligible,
        )
        status = _classify_graduation_status(
            latest_visible,
            target_period,
            academic_state,
            is_eligible,
            is_graduated,
            steps_remaining,
        )
        latest_visible_profiles.append(
            {
                "history": history,
                "record": latest_visible,
                "visible_registrations": visible_registrations,
                "target_period": target_period,
                "is_eligible": is_eligible,
                "steps_remaining": steps_remaining,
                "is_graduated": is_graduated,
                "academic_state": academic_state,
                "status": status,
                "graduation_stage_label": graduation_stage_label,
            }
        )
        logger.debug(
            "graduation.profile regnum=%s programme=%s target_period=%s chronological=%s eligible=%s graduated=%s status=%s attendance_type=%s",
            latest_visible["regnum"],
            latest_visible["programme_name"],
            target_period,
            latest_visible.get("chronological_progression_index"),
            is_eligible,
            is_graduated,
            status,
            _get_student_attendance_type(latest_visible["regnum"]),
        )

        if not is_graduated:
            logger.debug(
                "graduation.profile_skipped regnum=%s reason=not_graduated target_period=%s eligible=%s status=%s",
                latest_visible["regnum"],
                target_period,
                is_eligible,
                status,
            )
            continue

        effective_cohort_label = latest_visible["effective_cohort_label"]
        original_cohort_label = latest_visible["original_cohort_label"]
        actual_progression = latest_visible.get("relative_programme_progression_index", 0)
        steps_remaining = _steps_remaining(latest_visible, target_period)
        
        graduated_students.append(
            {
                "regnum": latest_visible["regnum"],
                "detail_slug": str(latest_visible["regnum"] or "").lower(),
                "student_name": latest_visible["student_name"],
                "programme_id": latest_visible["programme_id"],
                "programme_name": latest_visible["programme_name"],
                "department_name": latest_visible.get("department_name", "Unknown"),
                "faculty": latest_visible["faculty_name"],
                "is_graduated": True,  # This record represents a graduated student
                "on_time": effective_cohort_label == original_cohort_label,
                "target_period": target_period,
                "actual_progression": actual_progression,
                "chronological_progression_index": int(latest_visible.get("chronological_progression_index", 0) or 0),
                "steps_remaining": steps_remaining,
                "graduation_stage": graduation_stage_label,
                "graduation_period_label": graduation_stage_label,
                "target_graduation_stage": _graduation_stage_label(latest_visible["programme_name"], latest_visible["regnum"]),
                "target_graduation_period_label": _graduation_period_label(latest_visible["programme_name"], latest_visible["regnum"]),
                "effective_cohort": effective_cohort_label,
                "original_cohort": original_cohort_label,
                "period_external_id": latest_visible["period_external_id"],
                "status": status,
            }
        )

    graduated_students.sort(
        key=lambda row: _student_name_sort_key(row["student_name"], row["regnum"])
    )
    if not latest_visible_profiles:
        return _empty_graduation_payload()

    readiness_profiles = [
        profile
        for profile in latest_visible_profiles
        if (
            not profile["is_graduated"]
            and not profile["is_eligible"]
            and profile["steps_remaining"] is not None
            and profile["steps_remaining"] >= 0
        )
    ]
    one_step_profiles = [profile for profile in readiness_profiles if profile["steps_remaining"] <= 1]
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
    eligible_profiles = [profile for profile in latest_visible_profiles if profile["is_eligible"]]
    non_eligible_profiles = [profile for profile in latest_visible_profiles if not profile["is_eligible"]]
    near_eligible_profiles = [profile for profile in latest_visible_profiles if profile["status"] == "near_eligible"]
    delayed_profiles = [profile for profile in latest_visible_profiles if profile["status"] == "delayed"]
    active_profiles = [profile for profile in latest_visible_profiles if profile["status"] == "active"]
    at_risk_profiles = [profile for profile in latest_visible_profiles if profile["status"] == "at_risk"]
    eligible_profile_regnums = {profile["record"]["regnum"] for profile in eligible_profiles}
    eligible_graduated_students = [
        student
        for student in graduated_students
        if student["regnum"] in eligible_profile_regnums
    ]
    eligible_graduated_regnums = {student["regnum"] for student in eligible_graduated_students}
    eligible_students_count = len(eligible_profiles)
    non_eligible_students_count = len(non_eligible_profiles)

    average_graduation_rate = _safe_rate(len(eligible_graduated_students), eligible_students_count)
    on_time_graduation_rate = _safe_rate(
        sum(
            1
            for student in eligible_graduated_students
            if student["on_time"] and int(student.get("chronological_progression_index", 0) or 0) <= int(student["target_period"])
        ),
        len(eligible_graduated_students),
    )

    programme_rates: Dict[tuple[int, str], List[float]] = defaultdict(list)
    cohort_graduated: Dict[str, int] = defaultdict(int)
    timing_counts = {"On-time": 0, "Delayed": 0}

    visible_cohort_population: Dict[str, set[str]] = defaultdict(set)
    visible_faculty_population: Dict[str, set[str]] = defaultdict(set)
    visible_programme_population: Dict[tuple[int, str], set[str]] = defaultdict(set)
    faculty_cohort_population: Dict[str, Dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    faculty_cohort_graduated: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    original_cohort_eligible: Dict[str, set[str]] = defaultdict(set)
    programme_eligible_population: Dict[tuple[int, str], set[str]] = defaultdict(set)
    faculty_eligible_students: Dict[str, int] = defaultdict(int)
    programme_eligible_students: Dict[str, int] = defaultdict(int)

    for profile in latest_visible_profiles:
        record = profile["record"]
        regnum = record["regnum"]
        faculty_name = record["faculty_name"]
        cohort_label = record["original_cohort_label"]
        programme_key = (record["programme_id"], record["programme_name"])

        visible_cohort_population[cohort_label].add(regnum)
        visible_faculty_population[faculty_name].add(regnum)
        visible_programme_population[programme_key].add(regnum)

    for profile in eligible_profiles:
        record = profile["record"]
        regnum = record["regnum"]
        faculty_name = record["faculty_name"]
        cohort_label = record["original_cohort_label"]
        programme_key = (record["programme_id"], record["programme_name"])

        faculty_cohort_population[faculty_name][cohort_label].add(regnum)
        original_cohort_eligible[cohort_label].add(regnum)
        programme_eligible_population[programme_key].add(regnum)

    for faculty_name in visible_faculty_population:
        faculty_eligible_students[faculty_name] = len(
            {regnum for cohort_students in faculty_cohort_population[faculty_name].values() for regnum in cohort_students}
        )
    for programme_key, students in visible_programme_population.items():
        programme_eligible_students[programme_key[1]] = len(programme_eligible_population.get(programme_key, set()))

    for student in eligible_graduated_students:
        faculty_name = student["faculty"]
        cohort_label = student["original_cohort"]
        programme_rates[(student["programme_id"], student["programme_name"])].append(0)  # No individual graduation rate
        cohort_graduated[cohort_label] += 1
        faculty_cohort_graduated[faculty_name][cohort_label] += 1

    for student in graduated_students:
        graduated_on_time = student["on_time"] and int(student.get("chronological_progression_index", 0) or 0) <= int(student["target_period"])
        timing_counts["On-time" if graduated_on_time else "Delayed"] += 1

    graduation_rate_by_faculty: Dict[str, float] = {}
    faculty_cohort_details: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for faculty_name in visible_faculty_population:
        total_faculty_eligible = 0
        total_faculty_graduated = 0
        
        for cohort_label, student_numbers in faculty_cohort_population[faculty_name].items():
            cohort_total = len(student_numbers)
            cohort_graduated_count = faculty_cohort_graduated[faculty_name].get(cohort_label, 0)
            visible_cohort_total = len(visible_cohort_population.get(cohort_label, set()))
            cohort_rate = _safe_rate(cohort_graduated_count, cohort_total)
            
            # Add to faculty totals for weighted aggregation across eligible students only.
            total_faculty_eligible += cohort_total
            total_faculty_graduated += cohort_graduated_count
            
            # Extract cohort year from label (e.g., "May 2020 - August 2020" -> 2020)
            cohort_year = cohort_label.split()[1] if len(cohort_label.split()) > 1 else cohort_label
            
            faculty_cohort_details[faculty_name].append({
                "year": int(cohort_year) if cohort_year.isdigit() else 0,
                "cohort_label": cohort_label,
                "total_students": cohort_total,
                "eligible_students": cohort_total,
                "visible_students": visible_cohort_total,
                "graduated": cohort_graduated_count,
                "graduation_rate": cohort_rate
            })
        
        faculty_overall_rate = _safe_rate(total_faculty_graduated, total_faculty_eligible)
        graduation_rate_by_faculty[faculty_name] = faculty_overall_rate
        
        faculty_cohort_details[faculty_name].sort(key=lambda x: x["year"])
    
    best_faculty_name = ""
    best_faculty_rate = 0.0
    if graduation_rate_by_faculty:
        best_faculty_name, best_faculty_rate = max(
            graduation_rate_by_faculty.items(),
            key=lambda item: item[1],
        )

    programme_cohort_stats: Dict[tuple[int, str], Dict[str, Any]] = {}
    
    for student in eligible_graduated_students:
        programme_key = (student["programme_id"], student["programme_name"])
        cohort_label = student["original_cohort"]
        
        if programme_key not in programme_cohort_stats:
            programme_cohort_stats[programme_key] = {
                "total_graduated": 0,
                "cohorts": set()
            }
        
        programme_cohort_stats[programme_key]["total_graduated"] += 1
        programme_cohort_stats[programme_key]["cohorts"].add(cohort_label)
    
    programme_graduation_rate = []
    for (programme_id, programme_name), visible_students in visible_programme_population.items():
        stats = programme_cohort_stats.get(
            (programme_id, programme_name),
            {"total_graduated": 0, "cohorts": set()},
        )
        eligible_students = programme_eligible_population.get((programme_id, programme_name), set())
        graduation_rate = _safe_rate(stats["total_graduated"], len(eligible_students))
        programme_graduation_rate.append({
            "programme_id": programme_id,
            "programme_name": programme_name,
            "graduation_rate": graduation_rate,
            "graduated_count": stats["total_graduated"],
            "enrolled_count": len(visible_students),
            "eligible_students_count": len(eligible_students),
            "official_graduated_count": stats["total_graduated"],
        })
    
    programme_graduation_rate.sort(key=lambda row: row["graduation_rate"], reverse=True)

    cohort_graduation_rate = [
        {
            "original_cohort_label": cohort_label,
            "effective_cohort_sort_index": cohort_sort_indexes.get(cohort_label, 0),
            "graduated_count": cohort_graduated.get(cohort_label, 0),
            "enrolled_count": len(student_numbers),
            "eligible_students_count": len(original_cohort_eligible.get(cohort_label, set())),
            "graduation_rate": _safe_rate(
                cohort_graduated.get(cohort_label, 0),
                len(original_cohort_eligible.get(cohort_label, set())),
            ),
            "official_graduated_count": cohort_graduated.get(cohort_label, 0),
        }
        for cohort_label, student_numbers in sorted(
            visible_cohort_population.items(),
            key=lambda item: (
                cohort_sort_indexes.get(item[0], 0),
                item[0],
            ),
        )
    ]

    faculty_graduation_rate = []
    for faculty_name, rate in sorted(
        graduation_rate_by_faculty.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        total_faculty_eligible = len(
            {regnum for cohort_students in faculty_cohort_population[faculty_name].values() for regnum in cohort_students}
        )
        total_faculty_students = len(visible_faculty_population.get(faculty_name, set()))
        total_faculty_graduated = sum(faculty_cohort_graduated[faculty_name].values())
        
        faculty_data = {
            "faculty": faculty_name,
            "graduation_rate": round(rate, 0),
            "graduated_count": total_faculty_graduated,
            "enrolled_count": total_faculty_students,
            "eligible_students_count": total_faculty_eligible,
            "official_graduated_count": total_faculty_graduated,
            "cohorts": faculty_cohort_details[faculty_name],
            "overall_rate": round(rate, 0),
            "hierarchy": {
                "departments": [],
                "programmes": []
            }
        }
        
        department_stats = defaultdict(lambda: {"enrolled": set(), "graduated": set()})
        programme_stats = defaultdict(lambda: {"enrolled": set(), "graduated": set()})
        
        faculty_profiles = [
            profile
            for profile in eligible_profiles
            if profile["record"]["faculty_name"] == faculty_name
        ]

        for profile in faculty_profiles:
            regnum = profile["record"]["regnum"]
            student_record = profile["record"]
            dept_name = student_record.get("department_name", "Unknown")
            department_stats[dept_name]["enrolled"].add(regnum)

            prog_name = student_record.get("programme_name", "Unknown")
            programme_stats[prog_name]["enrolled"].add(regnum)

            if regnum in eligible_graduated_regnums:
                department_stats[dept_name]["graduated"].add(regnum)
                programme_stats[prog_name]["graduated"].add(regnum)

        for dept_name, stats in department_stats.items():
            visible_dept_total = len(
                {
                    profile["record"]["regnum"]
                    for profile in latest_visible_profiles
                    if profile["record"].get("department_name", "Unknown") == dept_name
                    and profile["record"]["faculty_name"] == faculty_name
                }
            )
            dept_rate = _safe_rate(len(stats["graduated"]), len(stats["enrolled"]))
            faculty_data["hierarchy"]["departments"].append({
                "department": dept_name,
                "graduation_rate": dept_rate,
                "graduated_count": len(stats["graduated"]),
                "enrolled_count": visible_dept_total,
                "eligible_students_count": len(stats["enrolled"]),
                "official_graduated_count": len(stats["graduated"]),
                "faculty": faculty_name
            })

        for prog_name, stats in programme_stats.items():
            visible_prog_total = len(
                {
                    profile["record"]["regnum"]
                    for profile in latest_visible_profiles
                    if profile["record"]["programme_name"] == prog_name
                    and profile["record"]["faculty_name"] == faculty_name
                }
            )
            prog_rate = _safe_rate(len(stats["graduated"]), len(stats["enrolled"]))

            prog_profiles = [profile for profile in faculty_profiles if profile["record"]["programme_name"] == prog_name]
            dept_name = prog_profiles[0]["record"].get("department_name", "Unknown") if prog_profiles else "Unknown"

            faculty_data["hierarchy"]["programmes"].append({
                "programme": prog_name,
                "graduation_rate": prog_rate,
                "graduated_count": len(stats["graduated"]),
                "enrolled_count": visible_prog_total,
                "eligible_students_count": len(stats["enrolled"]),
                "official_graduated_count": len(stats["graduated"]),
                "faculty": faculty_name,
                "department": dept_name
            })
        
        faculty_graduation_rate.append(faculty_data)

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
            "eligible_students_count": eligible_students_count,
            "non_eligible_students_count": non_eligible_students_count,
            "graduated_students_count": total_graduated_students,
            "official_graduated_count": total_graduated_students,
            "on_time_graduates": sum(
                1
                for student in eligible_graduated_students
                if student["on_time"] and int(student.get("chronological_progression_index", 0) or 0) <= int(student["target_period"])
            ),
            "delayed_graduates": sum(
                1
                for student in eligible_graduated_students
                if not (student["on_time"] and int(student.get("chronological_progression_index", 0) or 0) <= int(student["target_period"]))
            ),
            "near_eligible_students_count": len(near_eligible_profiles),
            "delayed_students_count": len(delayed_profiles),
            "active_students_count": len(active_profiles),
            "at_risk_students_count": len(at_risk_profiles),
            "faculty_eligible_students": dict(sorted(faculty_eligible_students.items())),
            "programme_eligible_students": dict(sorted(programme_eligible_students.items())),
        },
        "students": [
            {
                "regnum": student["regnum"],
                "detail_slug": student["detail_slug"],
                "student_name": student["student_name"],
                "programme_name": student["programme_name"],
                "department_name": student.get("department_name", "Unknown"),
                "faculty": student["faculty"],
                "is_graduated": student["is_graduated"],
                "on_time": student["on_time"],
                "target_period": student["target_period"],
                "actual_progression": student["actual_progression"],
                "steps_remaining": student["steps_remaining"],
                "graduation_stage": student["graduation_stage"],
                "graduation_period_label": student["graduation_period_label"],
                "target_graduation_stage": student["target_graduation_stage"],
                "target_graduation_period_label": student["target_graduation_period_label"],
                "effective_cohort": student["effective_cohort"],
                "original_cohort": student["original_cohort"],
                # Backward compatibility: individual graduation rate (100% for graduated students)
                "graduation_rate": 100.0 if student["is_graduated"] else 0.0,
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


GRADUATION_CACHE_TTL_SECONDS = 300


def _build_graduation_cache_key(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> str:
    parts = [year or "all", period or "all", faculty or "all"]
    return f"dashboard:graduation:{'_'.join(parts)}"


def get_cached_graduation_page_data(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return cached graduation analytics, rebuilding only on cold miss or TTL expiry."""

    cache_key = _build_graduation_cache_key(year, period, faculty)
    result = cache.get(cache_key)
    if result is None:
        result = get_graduation_page_data(year=year, period=period, faculty=faculty)
        cache.set(cache_key, result, GRADUATION_CACHE_TTL_SECONDS)
    return result


def get_cached_graduation_fast_metrics(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return graduation KPIs from payload cache when warm; empty placeholder on cold miss."""

    payload_cache_key = _build_graduation_cache_key(year, period, faculty)
    cached_payload = cache.get(payload_cache_key)
    if cached_payload is not None:
        return {"kpis": cached_payload.get("kpis", {})}
    return {"kpis": {}}

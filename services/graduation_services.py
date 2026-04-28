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
    _target_period_cache[cache_key] = result
    return result


# Cache for attendance types to avoid repeated database queries
_attendance_type_cache: Dict[str, Optional[str]] = {}

# Cache for target periods and graduation stages
_target_period_cache: Dict[tuple[str, Optional[str]], int] = {}
_graduation_stage_cache: Dict[tuple[str, Optional[str]], str] = {}
_graduation_period_cache: Dict[tuple[str, Optional[str]], str] = {}

def _batch_get_attendance_types(student_regnums: List[str]) -> Dict[str, Optional[str]]:
    """Batch fetch attendance types for multiple students to reduce database queries."""
    try:
        from dashboard.models import Registration, CourseResult
        
        # Filter out already cached regnums
        uncached_regnums = [regnum for regnum in student_regnums if regnum not in _attendance_type_cache]
        if not uncached_regnums:
            return _attendance_type_cache
        
        # Get all registrations for uncached students in one query
        registrations = Registration.objects.filter(
            student__registration_number__in=uncached_regnums
        ).order_by('student__registration_number', '-period__external_id', '-id')
        
        # Group by student and get latest registration for each
        latest_registrations = {}
        for reg in registrations:
            regnum = reg.student.registration_number
            if regnum not in latest_registrations:
                latest_registrations[regnum] = reg
            # Since we ordered by latest first, the first occurrence is the latest
        
        # Mark students with no registrations
        for regnum in uncached_regnums:
            if regnum not in latest_registrations:
                _attendance_type_cache[regnum] = None
        
        # Batch fetch course results for all latest registrations
        if latest_registrations:
            registration_ids = [reg.id for reg in latest_registrations.values()]
            course_results = CourseResult.objects.filter(registration_id__in=registration_ids)
            course_results_map = {cr.registration_id: cr for cr in course_results}
            
            # Process results and cache them
            for regnum, registration in latest_registrations.items():
                course_result = course_results_map.get(registration.id)
                attendance_type = None
                if course_result and hasattr(course_result, 'attendance_type'):
                    attendance_type = course_result.attendance_type
                _attendance_type_cache[regnum] = attendance_type
        
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
    # Check for graduation decisions per user requirements
    return any(term in normalized for term in (
        "graduat", "complet", "award",  # Original criteria
        "pending", "proceed", "resubmit dissertation within 3 months"  # New criteria per user requirements
    ))


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
    decision_key = record.get("decision_key", "")
    
    # Student must meet BOTH criteria: complete semesters AND have valid decision
    if progression_period is not None and progression_period >= target_period and _decision_indicates_graduation(decision_key):
        return True
    return False


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
        target_period = _target_period_from_programme(latest_visible["programme_name"], latest_visible["regnum"])
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
        actual_progression = latest_visible.get("relative_programme_progression_index", 0)
        steps_remaining = _steps_remaining(latest_visible, target_period)
        
        graduated_students.append(
            {
                "regnum": latest_visible["regnum"],
                "student_name": latest_visible["student_name"],
                "programme_id": latest_visible["programme_id"],
                "programme_name": latest_visible["programme_name"],
                "faculty": latest_visible["faculty_name"],
                "is_graduated": True,  # This record represents a graduated student
                "on_time": effective_cohort_label == original_cohort_label,
                "target_period": target_period,
                "actual_progression": actual_progression,
                "steps_remaining": steps_remaining,
                "graduation_stage": _graduation_stage_label(latest_visible["programme_name"], latest_visible["regnum"]),
                "graduation_period_label": _graduation_period_label(latest_visible["programme_name"], latest_visible["regnum"]),
                "effective_cohort": effective_cohort_label,
                "original_cohort": original_cohort_label,
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
    # Calculate average graduation rate using cohort-based logic (not individual rates)
    # This will be calculated later after we compute cohort rates
    average_graduation_rate = 0.0  # Will be updated after cohort calculations
    on_time_graduation_rate = _safe_rate(
        sum(1 for student in graduated_students if student["on_time"]),
        total_graduated_students,
    )

    programme_rates: Dict[tuple[int, str], List[float]] = defaultdict(list)
    cohort_graduated: Dict[str, int] = defaultdict(int)
    timing_counts = {"On-time": 0, "Delayed": 0}

    # Build faculty-cohort-student mapping for strict cohort isolation using original_cohort
    faculty_cohort_population: Dict[str, Dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    faculty_cohort_graduated: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Populate faculty-cohort population (all students) using original_cohort
    for history in student_histories:
        faculty_name = history["latest_record"]["faculty_name"]
        cohort_label = history["latest_record"]["original_cohort_label"]
        regnum = history["regnum"]
        faculty_cohort_population[faculty_name][cohort_label].add(regnum)

    # Populate faculty-cohort graduated (only graduated students) using original_cohort
    for student in graduated_students:
        faculty_name = student["faculty"]
        cohort_label = student["original_cohort"]
        programme_rates[(student["programme_id"], student["programme_name"])].append(0)  # No individual graduation rate
        cohort_graduated[student["original_cohort"]] += 1
        timing_counts["On-time" if student["on_time"] else "Delayed"] += 1
        faculty_cohort_graduated[faculty_name][cohort_label] += 1

    # Calculate faculty graduation rates with strict cohort isolation and weighted aggregation
    graduation_rate_by_faculty: Dict[str, float] = {}
    faculty_cohort_details: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for faculty_name in faculty_cohort_population:
        total_faculty_students = 0
        total_faculty_graduated = 0
        
        for cohort_label, student_numbers in faculty_cohort_population[faculty_name].items():
            cohort_total = len(student_numbers)
            cohort_graduated_count = faculty_cohort_graduated[faculty_name].get(cohort_label, 0)
            cohort_rate = _safe_rate(cohort_graduated_count, cohort_total)
            
            # Add to faculty totals for weighted aggregation
            total_faculty_students += cohort_total
            total_faculty_graduated += cohort_graduated_count
            
            # Extract cohort year from label (e.g., "May 2020 - August 2020" -> 2020)
            cohort_year = cohort_label.split()[1] if len(cohort_label.split()) > 1 else cohort_label
            
            faculty_cohort_details[faculty_name].append({
                "year": int(cohort_year) if cohort_year.isdigit() else 0,
                "cohort_label": cohort_label,
                "total_students": cohort_total,
                "graduated": cohort_graduated_count,
                "graduation_rate": cohort_rate
            })
        
        # Calculate weighted faculty graduation rate
        faculty_overall_rate = _safe_rate(total_faculty_graduated, total_faculty_students)
        graduation_rate_by_faculty[faculty_name] = faculty_overall_rate
        
        # Sort cohorts by year
        faculty_cohort_details[faculty_name].sort(key=lambda x: x["year"])
    
    # Calculate overall average graduation rate using cohort-based logic
    total_all_students = sum(len(students) for students in original_cohort_enrollment.values())
    average_graduation_rate = _safe_rate(total_graduated_students, total_all_students)
    
    best_faculty_name = ""
    best_faculty_rate = 0.0
    if total_graduated_students and graduation_rate_by_faculty:
        best_faculty_name, best_faculty_rate = max(
            graduation_rate_by_faculty.items(),
            key=lambda item: item[1],
        )

    # Calculate programme graduation rates using cohort-based logic
    programme_cohort_stats: Dict[tuple[int, str], Dict[str, Any]] = {}
    
    for student in graduated_students:
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
    for (programme_id, programme_name), stats in programme_cohort_stats.items():
        # Calculate total students in this programme across all cohorts
        total_programme_students = 0
        for cohort in stats["cohorts"]:
            total_programme_students += len(original_cohort_enrollment.get(cohort, set()))
        
        graduation_rate = _safe_rate(stats["total_graduated"], total_programme_students)
        programme_graduation_rate.append({
            "programme_id": programme_id,
            "programme_name": programme_name,
            "graduation_rate": graduation_rate,
            "graduated_count": stats["total_graduated"],
        })
    
    programme_graduation_rate.sort(key=lambda row: row["graduation_rate"], reverse=True)

    cohort_graduation_rate = [
        {
            "original_cohort_label": cohort_label,
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

    faculty_graduation_rate = []
    for faculty_name, rate in sorted(
        graduation_rate_by_faculty.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        # Calculate total faculty students and graduates for this faculty
        total_faculty_students = sum(len(students) for students in faculty_cohort_population[faculty_name].values())
        total_faculty_graduated = sum(faculty_cohort_graduated[faculty_name].values())
        
        # Build hierarchical data structure
        faculty_data = {
            "faculty": faculty_name,
            "graduation_rate": round(rate, 0),
            "graduated_count": total_faculty_graduated,
            "enrolled_count": total_faculty_students,
            "cohorts": faculty_cohort_details[faculty_name],
            "overall_rate": round(rate, 0),
            "hierarchy": {
                "departments": [],
                "programmes": []
            }
        }
        
        # Add department level data using student histories
        department_stats = defaultdict(lambda: {"enrolled": set(), "graduated": set()})
        programme_stats = defaultdict(lambda: {"enrolled": set(), "graduated": set()})
        
        # Get student histories for this faculty
        faculty_histories = [h for h in student_histories if h["latest_record"]["faculty_name"] == faculty_name]
        
        # Create a set of graduated registration numbers for this faculty
        graduated_regnums = set()
        for student in graduated_students:
            if student["faculty"] == faculty_name:
                graduated_regnums.add(student["regnum"])
        
        for history in faculty_histories:
            regnum = history["regnum"]
            student_record = history["latest_record"]
            
            # Department level
            dept_name = student_record.get("department_name", "Unknown")
            department_stats[dept_name]["enrolled"].add(regnum)
            
            # Programme level  
            prog_name = student_record.get("programme_name", "Unknown")
            programme_stats[prog_name]["enrolled"].add(regnum)
            
            # Check if graduated
            if regnum in graduated_regnums:
                department_stats[dept_name]["graduated"].add(regnum)
                programme_stats[prog_name]["graduated"].add(regnum)
        
        # Calculate department graduation rates
        for dept_name, stats in department_stats.items():
            dept_rate = _safe_rate(len(stats["graduated"]), len(stats["enrolled"]))
            faculty_data["hierarchy"]["departments"].append({
                "department": dept_name,
                "graduation_rate": dept_rate,
                "graduated_count": len(stats["graduated"]),
                "enrolled_count": len(stats["enrolled"]),
                "faculty": faculty_name
            })
        
        # Calculate programme graduation rates
        for prog_name, stats in programme_stats.items():
            prog_rate = _safe_rate(len(stats["graduated"]), len(stats["enrolled"]))
            
            # Get department for this programme
            prog_histories = [h for h in faculty_histories if h["latest_record"]["programme_name"] == prog_name]
            dept_name = prog_histories[0]["latest_record"].get("department_name", "Unknown") if prog_histories else "Unknown"
            
            faculty_data["hierarchy"]["programmes"].append({
                "programme": prog_name,
                "graduation_rate": prog_rate,
                "graduated_count": len(stats["graduated"]),
                "enrolled_count": len(stats["enrolled"]),
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
        },
        "students": [
            {
                "regnum": student["regnum"],
                "student_name": student["student_name"],
                "programme_name": student["programme_name"],
                "faculty": student["faculty"],
                "is_graduated": student["is_graduated"],
                "on_time": student["on_time"],
                "target_period": student["target_period"],
                "actual_progression": student["actual_progression"],
                "steps_remaining": student["steps_remaining"],
                "graduation_stage": student["graduation_stage"],
                "graduation_period_label": student["graduation_period_label"],
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

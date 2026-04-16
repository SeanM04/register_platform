"""Database-backed completion analysis service."""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.db.models import Prefetch

from dashboard.models import CourseResult, Registration


PASS_MARK = 50


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _safe_rate(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _normalise_gender(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("m"):
        return "male"
    if normalized.startswith("f"):
        return "female"
    return "other"


def _infer_programme_duration(programme_name: str) -> int:
    normalized = str(programme_name or "").lower()
    if "master" in normalized or "msc" in normalized or "mba" in normalized:
        return 2
    if "engineering" in normalized:
        return 5
    return 4


def _build_stage_label(registration: Registration) -> str:
    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    if year and semester:
        return f"Year {year}, Semester {semester}"
    if registration.period.academic_year and registration.period.semester:
        return f"Year {registration.period.academic_year}, Semester {registration.period.semester}"
    return registration.period.name


def _progress_rate(registration: Registration) -> float:
    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    duration = _infer_programme_duration(registration.programme.name)
    if year is None or semester is None or semester <= 0:
        return 0.0

    total_slots = max(duration * 2, 1)
    current_slot = max(((year - 1) * 2) + semester, 1)
    return round(min(current_slot / total_slots, 1.0) * 100, 1)


def _registration_marks(registration: Registration) -> List[float]:
    marks: List[float] = []
    for result in getattr(registration, "prefetched_course_results", []):
        if result.mark is None:
            continue
        marks.append(float(result.mark))
    return marks


def _pass_rate_for_registrations(registrations: List[Registration]) -> float:
    marks = [mark for registration in registrations for mark in _registration_marks(registration)]
    if not marks:
        return 0.0
    passed = sum(1 for mark in marks if mark >= PASS_MARK)
    return _safe_rate(passed, len(marks))


def _is_completed(registration: Registration) -> bool:
    decision = str(registration.decision or "").strip().lower()
    if "graduat" in decision or "complet" in decision:
        return True

    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    duration = _infer_programme_duration(registration.programme.name)
    return bool(year and semester and semester == 2 and year >= duration)


def _student_profile(registrations: List[Registration]) -> Dict[str, Any]:
    latest = max(registrations, key=lambda registration: (registration.period.external_id, registration.id))
    pass_rate = _pass_rate_for_registrations(registrations)
    progress_rate = _progress_rate(latest)
    completion_rate = round(((progress_rate * 0.55) + (pass_rate * 0.45)), 1) if pass_rate else progress_rate
    graduation_rate = 100.0 if _is_completed(latest) else None

    return {
        "regnum": latest.student.registration_number,
        "student_name": latest.student.full_name,
        "programme_name": latest.programme.normalized_name,
        "academic_stage": _build_stage_label(latest),
        "decision": latest.decision or "Pending",
        "completion_rate": completion_rate,
        "graduation_rate": graduation_rate,
        "gender_key": _normalise_gender(latest.student.gender),
        "period_external_id": latest.period.external_id,
        "registration_number": latest.student.registration_number,
        "detail_slug": latest.student.registration_number.lower(),
    }


def _get_filtered_registrations(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> List[Registration]:
    registrations = (
        Registration.objects.select_related(
            "student",
            "programme__department__faculty",
            "period",
        )
        .prefetch_related(
            Prefetch(
                "course_results",
                queryset=CourseResult.objects.only("registration_id", "mark"),
                to_attr="prefetched_course_results",
            )
        )
        .all()
    )

    # Handle combined year and period filtering
    if year and period:
        # Both year and period provided - filter by exact period name
        registrations = registrations.filter(period__name=str(period))
    elif year:
        # Only year provided - filter by academic year
        registrations = registrations.filter(period__academic_year=str(year))
    elif period:
        # Only period provided - filter by exact period name
        registrations = registrations.filter(period__name=str(period))
    
    if faculty:
        registrations = registrations.filter(programme__department__faculty__name=faculty)

    return list(registrations.order_by("student__registration_number", "period__external_id", "id"))


def get_completion_page_data(
    year: Optional[str] = None,
    period: Optional[str] = None,
    faculty: Optional[str] = None,
) -> Dict[str, Any]:
    """Return completion analytics directly from imported dashboard tables."""

    registrations = _get_filtered_registrations(
        year=year,
        period=period,
        faculty=faculty,
    )
    if not registrations:
        return {
            "kpis": {
                "total_students": 0,
                "total_cohorts": 0,
                "average_completion_rate": 0.0,
                "gender_distribution": {"male": 0, "female": 0, "other": 0},
            },
            "charts": {"cohort_completion": [], "programme_completion": []},
            "students": [],
        }

    registrations_by_student: Dict[str, List[Registration]] = defaultdict(list)
    for registration in registrations:
        registrations_by_student[registration.student.registration_number].append(registration)

    student_profiles = [
        _student_profile(student_registrations)
        for student_registrations in registrations_by_student.values()
    ]
    student_profiles.sort(key=lambda row: (row["student_name"], row["regnum"]))

    gender_distribution = {"male": 0, "female": 0, "other": 0}
    for profile in student_profiles:
        gender_distribution[profile["gender_key"]] += 1

    completion_average = round(
        sum(profile["completion_rate"] for profile in student_profiles) / len(student_profiles),
        1,
    ) if student_profiles else 0.0

    registrations_by_period: Dict[int, List[Registration]] = defaultdict(list)
    for registration in registrations:
        registrations_by_period[registration.period.external_id].append(registration)

    cohort_completion = []
    for period_external_id, period_registrations in sorted(registrations_by_period.items()):
        unique_students = {registration.student.registration_number for registration in period_registrations}
        avg_completion = round(
            sum(_progress_rate(registration) for registration in period_registrations) / len(period_registrations),
            1,
        ) if period_registrations else 0.0
        cohort_completion.append(
            {
                "cohort_period_id": period_external_id,
                "initial_students": len(unique_students),
                "current_students": len(unique_students),
                "completion_rate": avg_completion,
            }
        )

    latest_profiles_by_programme: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for profile in student_profiles:
        latest_registration = max(
            registrations_by_student[profile["regnum"]],
            key=lambda registration: (registration.period.external_id, registration.id),
        )
        latest_profiles_by_programme[latest_registration.programme.external_id or latest_registration.programme.id].append(
            {
                "programme_id": latest_registration.programme.external_id or latest_registration.programme.id,
                "programme_name": latest_registration.programme.normalized_name,
                "completion_rate": profile["completion_rate"],
            }
        )

    programme_completion = []
    for programme_profiles in latest_profiles_by_programme.values():
        first_profile = programme_profiles[0]
        programme_completion.append(
            {
                "programme_id": first_profile["programme_id"],
                "programme_name": first_profile["programme_name"],
                "completion_rate": round(
                    sum(profile["completion_rate"] for profile in programme_profiles) / len(programme_profiles),
                    1,
                ),
            }
        )
    programme_completion.sort(key=lambda row: row["completion_rate"], reverse=True)

    return {
        "kpis": {
            "total_students": len(student_profiles),
            "total_cohorts": len(registrations_by_period),
            "average_completion_rate": completion_average,
            "gender_distribution": gender_distribution,
        },
        "charts": {
            "cohort_completion": cohort_completion,
            "programme_completion": programme_completion,
        },
        "students": [
            {
                "regnum": profile["regnum"],
                "student_name": profile["student_name"],
                "programme_name": profile["programme_name"],
                "academic_stage": profile["academic_stage"],
                "decision": profile["decision"],
                "completion_rate": profile["completion_rate"],
                "graduation_rate": profile["graduation_rate"],
                "detail_slug": profile["detail_slug"],
            }
            for profile in student_profiles
        ],
    }


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

    years = (
        Registration.objects.select_related("period")
        .values_list("period__academic_year", flat=True)
        .distinct()
        .order_by("period__academic_year")
    )
    # Clean up years and convert to proper format
    clean_years = []
    for year in years:
        year_str = str(year).strip()
        if year_str and year_str.isdigit():
            # Convert to proper year format (e.g., "1" -> "Year 1")
            clean_years.append({"year": f"Year {year_str}", "value": year_str})
    return clean_years


def get_completion_periods() -> List[Dict[str, Any]]:
    """Return period options in the shape expected by the completion page."""

    periods = (
        Registration.objects.select_related("period")
        .values_list("period__name", flat=True)
        .distinct()
        .order_by("period__name")
    )
    # Clean up periods and provide both display and value
    clean_periods = []
    for period in periods:
        period_str = str(period).strip()
        if period_str:
            clean_periods.append({"period": period_str, "value": period_str})
    return clean_periods


def get_completion_periods_by_year() -> List[Dict[str, Any]]:
    """Return periods grouped by academic year for frontend mapping."""
    
    # Get all periods with their academic years
    periods_data = (
        Registration.objects.select_related("period")
        .values_list("period__name", "period__academic_year")
        .distinct()
        .order_by("period__academic_year", "period__name")
    )
    
    # Group periods by academic year
    periods_by_year = {}
    for period_name, academic_year in periods_data:
        year_str = str(academic_year).strip()
        period_str = str(period_name).strip()
        
        if year_str and period_str and year_str.isdigit():
            year_key = f"Year {year_str}"
            if year_key not in periods_by_year:
                periods_by_year[year_key] = {
                    "year": year_key,
                    "value": year_str,
                    "periods": []
                }
            periods_by_year[year_key]["periods"].append({
                "period": period_str,
                "value": period_str
            })
    
    # Convert to sorted list
    return list(periods_by_year.values())

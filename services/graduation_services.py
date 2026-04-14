"""Database-backed graduation analysis service."""

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


def _infer_programme_duration(programme_name: str) -> int:
    normalized = str(programme_name or "").lower()
    if "master" in normalized or "msc" in normalized or "mba" in normalized:
        return 2
    if "engineering" in normalized:
        return 5
    return 4


def _graduation_stage(registration: Registration) -> str:
    duration = _infer_programme_duration(registration.programme.name)
    return f"{duration}.2"


def _registration_marks(registration: Registration) -> List[float]:
    marks: List[float] = []
    for result in getattr(registration, "prefetched_course_results", []):
        if result.mark is None:
            continue
        marks.append(float(result.mark))
    return marks


def _pass_rate(registrations: List[Registration]) -> float:
    marks = [mark for registration in registrations for mark in _registration_marks(registration)]
    if not marks:
        return 0.0
    passed = sum(1 for mark in marks if mark >= PASS_MARK)
    return _safe_rate(passed, len(marks))


def _is_graduated(registration: Registration) -> bool:
    decision = str(registration.decision or "").strip().lower()
    if "graduat" in decision or "complet" in decision or "award" in decision:
        return True

    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    duration = _infer_programme_duration(registration.programme.name)
    return bool(year and semester == 2 and year >= duration)


def _is_on_time(registration: Registration) -> bool:
    if not _is_graduated(registration):
        return False

    year = _parse_int(registration.period.academic_year)
    semester = _parse_int(registration.period.semester)
    duration = _infer_programme_duration(registration.programme.name)
    return bool(year and semester and semester == 2 and year == duration)


def _student_graduation_rate(registrations: List[Registration]) -> float:
    latest = max(registrations, key=lambda registration: (registration.period.external_id, registration.id))
    academic_pass_rate = _pass_rate(registrations)
    if _is_graduated(latest):
        if academic_pass_rate:
            return round(max(academic_pass_rate, 85.0), 1)
        return 90.0

    year = _parse_int(latest.period.academic_year)
    semester = _parse_int(latest.period.semester)
    duration = _infer_programme_duration(latest.programme.name)
    if year is None or semester is None:
        return academic_pass_rate
    progress = min((((year - 1) * 2) + semester) / (duration * 2), 1.0) * 100
    return round(((progress * 0.5) + (academic_pass_rate * 0.5)), 1) if academic_pass_rate else round(progress, 1)


def _get_filtered_registrations(
    faculty: Optional[str] = None,
    programme_id: Optional[str] = None,
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

    if faculty:
        registrations = registrations.filter(programme__department__faculty__name=faculty)
    if programme_id:
        registrations = registrations.filter(programme__external_id=_parse_int(programme_id))

    return list(registrations.order_by("student__registration_number", "period__external_id", "id"))


def get_graduation_page_data(
    faculty: Optional[str] = None,
    programme_id: Optional[str] = None,
    graduation_stage: Optional[str] = None,
    min_rate: Optional[str] = None,
) -> Dict[str, Any]:
    """Return graduation analytics directly from imported dashboard tables."""

    registrations = _get_filtered_registrations(faculty=faculty, programme_id=programme_id)
    if not registrations:
        return {
            "kpis": {
                "total_graduated_students": 0,
                "average_completion_graduation_rate": 0.0,
                "on_time_graduation_rate": 0.0,
                "graduation_rate_by_faculty": {},
            },
            "charts": {"programme_graduation_rate": [], "cohort_graduation_rate": []},
            "students": [],
        }

    registrations_by_student: Dict[str, List[Registration]] = defaultdict(list)
    for registration in registrations:
        registrations_by_student[registration.student.registration_number].append(registration)

    latest_by_student = {
        student_number: max(student_registrations, key=lambda registration: (registration.period.external_id, registration.id))
        for student_number, student_registrations in registrations_by_student.items()
    }

    graduated_students = []
    for student_number, latest_registration in latest_by_student.items():
        student_registrations = registrations_by_student[student_number]
        graduation_rate = _student_graduation_rate(student_registrations)
        stage = _graduation_stage(latest_registration)
        if not _is_graduated(latest_registration):
            continue
        graduated_students.append(
            {
                "regnum": latest_registration.student.registration_number,
                "student_name": latest_registration.student.full_name,
                "programme_name": latest_registration.programme.normalized_name,
                "faculty": latest_registration.programme.department.faculty.name,
                "graduation_rate": graduation_rate,
                "graduation_stage": stage,
                "on_time": _is_on_time(latest_registration),
                "period_external_id": latest_registration.period.external_id,
                "programme_id": latest_registration.programme.external_id or latest_registration.programme.id,
            }
        )

    requested_stage = str(graduation_stage or "").strip()
    requested_min_rate = None
    try:
        requested_min_rate = float(min_rate) if str(min_rate).strip() else None
    except (TypeError, ValueError):
        requested_min_rate = None

    if requested_stage:
        graduated_students = [student for student in graduated_students if student["graduation_stage"] == requested_stage]
    if requested_min_rate is not None:
        graduated_students = [student for student in graduated_students if student["graduation_rate"] >= requested_min_rate]

    graduated_students.sort(key=lambda row: (row["student_name"], row["regnum"]))

    total_graduated = len(graduated_students)
    average_graduation_rate = round(
        sum(student["graduation_rate"] for student in graduated_students) / total_graduated,
        1,
    ) if total_graduated else 0.0
    on_time_rate = _safe_rate(sum(1 for student in graduated_students if student["on_time"]), total_graduated)

    faculty_population: Dict[str, set] = defaultdict(set)
    faculty_graduated: Dict[str, int] = defaultdict(int)
    for latest_registration in latest_by_student.values():
        faculty_name = latest_registration.programme.department.faculty.name
        faculty_population[faculty_name].add(latest_registration.student.registration_number)
        if _is_graduated(latest_registration):
            faculty_graduated[faculty_name] += 1
    faculty_rates = {
        faculty_name: _safe_rate(faculty_graduated.get(faculty_name, 0), len(student_numbers))
        for faculty_name, student_numbers in faculty_population.items()
    }

    programme_population: Dict[int, set] = defaultdict(set)
    programme_graduated: Dict[int, List[float]] = defaultdict(list)
    programme_names: Dict[int, str] = {}
    for latest_registration in latest_by_student.values():
        programme_key = latest_registration.programme.external_id or latest_registration.programme.id
        programme_population[programme_key].add(latest_registration.student.registration_number)
        programme_names[programme_key] = latest_registration.programme.normalized_name
    for student in graduated_students:
        programme_graduated[student["programme_id"]].append(student["graduation_rate"])

    programme_graduation_rate = []
    for programme_key, student_numbers in programme_population.items():
        graduated_count = len(programme_graduated.get(programme_key, []))
        programme_graduation_rate.append(
            {
                "programme_name": programme_names[programme_key],
                "graduation_rate": _safe_rate(graduated_count, len(student_numbers)),
            }
        )
    programme_graduation_rate.sort(key=lambda row: row["graduation_rate"], reverse=True)

    cohort_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: {"graduated": 0, "total": 0})
    for latest_registration in latest_by_student.values():
        cohort_counts[latest_registration.period.external_id]["total"] += 1
        if _is_graduated(latest_registration):
            cohort_counts[latest_registration.period.external_id]["graduated"] += 1
    cohort_graduation_rate = [
        {
            "cohort_period_id": period_external_id,
            "graduation_rate": _safe_rate(counts["graduated"], counts["total"]),
        }
        for period_external_id, counts in sorted(cohort_counts.items())
    ]

    return {
        "kpis": {
            "total_graduated_students": total_graduated,
            "average_completion_graduation_rate": average_graduation_rate,
            "on_time_graduation_rate": on_time_rate,
            "graduation_rate_by_faculty": faculty_rates,
        },
        "charts": {
            "programme_graduation_rate": programme_graduation_rate,
            "cohort_graduation_rate": cohort_graduation_rate,
        },
        "students": [
            {
                "regnum": student["regnum"],
                "student_name": student["student_name"],
                "programme_name": student["programme_name"],
                "faculty": student["faculty"],
                "graduation_rate": student["graduation_rate"],
                "graduation_stage": student["graduation_stage"],
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

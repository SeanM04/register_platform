"""Service-layer logic for academic-level analytics."""

from urllib.parse import urlencode

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.urls import reverse

from ..models import CourseResult, Registration
from ..student_history import (
    build_registration_display_level_index,
    build_registration_display_level_index_for_student_ids,
    build_student_timeline,
    extract_registration_year_semester,
)
from ..views import (
    GENDER_BUCKETS,
    get_filtered_registrations,
    normalize_gender_key,
)

from .constants import ACADEMIC_LEVEL_PASS_TARGET

ACADEMIC_LEVEL_CACHE_TTL_SECONDS = 30
ACADEMIC_LEVEL_DRILLDOWN_COLUMNS = [
    {"key": "name", "label": "Student"},
    {"key": "academic_level", "label": "Academic Level"},
    {"key": "programme", "label": "Programme"},
    {"key": "department", "label": "Department"},
    {"key": "gender", "label": "Gender"},
    {"key": "study_mode", "label": "Study Mode"},
    {"key": "average_mark", "label": "Average Mark"},
    {"key": "decision", "label": "Decision"},
]


def get_academic_level_registrations(request, search_query=""):
    """Return academic-level registrations shaped by the page filters and search."""

    registrations = (
        get_filtered_registrations(request, include_course_results=False)
        .select_related("attendance_type_record")
        .only(
            "id",
            "student_id",
            "student__id",
            "student__registration_number",
            "student__first_names",
            "student__surname",
            "student__gender",
            "programme_id",
            "programme__id",
            "programme__name",
            "programme__department_id",
            "programme__department__id",
            "programme__department__name",
            "programme__department__faculty_id",
            "programme__department__faculty__id",
            "programme__department__faculty__name",
            "period_id",
            "period__id",
            "period__academic_year",
            "period__semester",
            "attendance_type_id",
            "attendance_type_record_id",
            "attendance_type_record__name",
        )
        .prefetch_related(
            Prefetch(
                "course_results",
                queryset=CourseResult.objects.only("registration_id", "mark").order_by(),
                to_attr="prefetched_course_results",
            )
        )
    )
    if search_query:
        registrations = registrations.filter(
            Q(period__academic_year__icontains=search_query)
            | Q(period__semester__icontains=search_query)
            | Q(programme__name__icontains=search_query)
            | Q(programme__department__name__icontains=search_query)
        )

    return registrations


def build_academic_level_data(request, search_query=""):
    """Build table rows plus graph-ready academic-level breakdowns."""

    registrations = list(get_academic_level_registrations(request, search_query))
    registration_level_index = build_registration_display_level_index_for_student_ids(
        {registration.student_id for registration in registrations},
        faculty_name=request.GET.get("faculty", "").strip(),
    ) or build_registration_display_level_index(registrations)
    level_map = {}
    programme_map = {}
    gender_map = {
        key: {
            "label": label,
            "students": set(),
            "marks_total": 0,
            "mark_count": 0,
            "pass_count": 0,
        }
        for key, label in GENDER_BUCKETS
    }

    for registration in registrations:
        level_meta = registration_level_index.get(registration.id)
        if level_meta:
            year = level_meta["display_year"]
            semester = level_meta["display_semester"]
            level_label = level_meta["academic_level_label"]
        else:
            year, semester = extract_registration_year_semester(registration)
            level_label = f"Year {year} Semester {semester}"
        level_key = f"{year}.{semester}"
        gender_key = normalize_gender_key(registration.student.gender)
        programme_name = registration.programme.normalized_name

        if level_key not in level_map:
            level_map[level_key] = {
                "level": level_label,
                "sort_year": int(year) if str(year).isdigit() else 0,
                "sort_semester": int(semester) if str(semester).isdigit() else 0,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
                "programme_counts": {},
                "programme_breakdown": {},
                "gender_students": {key: set() for key, _ in GENDER_BUCKETS},
            }

        if programme_name not in programme_map:
            programme_map[programme_name] = {
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
                "level_counts": {},
                "level_breakdown": {},
            }

        level_map[level_key]["registrations"] += 1
        level_map[level_key]["students"].add(registration.student_id)
        level_map[level_key]["programme_counts"][programme_name] = (
            level_map[level_key]["programme_counts"].get(programme_name, 0) + 1
        )
        level_map[level_key]["gender_students"][gender_key].add(registration.student_id)

        if programme_name not in level_map[level_key]["programme_breakdown"]:
            level_map[level_key]["programme_breakdown"][programme_name] = {
                "programme": programme_name,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
            }

        level_map[level_key]["programme_breakdown"][programme_name]["registrations"] += 1
        level_map[level_key]["programme_breakdown"][programme_name]["students"].add(registration.student_id)

        gender_map[gender_key]["students"].add(registration.student_id)

        programme_map[programme_name]["registrations"] += 1
        programme_map[programme_name]["students"].add(registration.student_id)
        programme_map[programme_name]["level_counts"][level_label] = (
            programme_map[programme_name]["level_counts"].get(level_label, 0) + 1
        )

        if level_label not in programme_map[programme_name]["level_breakdown"]:
            programme_map[programme_name]["level_breakdown"][level_label] = {
                "level": level_label,
                "sort_year": int(year) if str(year).isdigit() else 0,
                "sort_semester": int(semester) if str(semester).isdigit() else 0,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
            }

        programme_map[programme_name]["level_breakdown"][level_label]["registrations"] += 1
        programme_map[programme_name]["level_breakdown"][level_label]["students"].add(registration.student_id)

        for result in registration.prefetched_course_results:
            if result.mark is None:
                continue
            mark_value = float(result.mark)

            level_map[level_key]["marks_total"] += mark_value
            level_map[level_key]["mark_count"] += 1
            level_map[level_key]["programme_breakdown"][programme_name]["marks_total"] += mark_value
            level_map[level_key]["programme_breakdown"][programme_name]["mark_count"] += 1
            gender_map[gender_key]["marks_total"] += mark_value
            gender_map[gender_key]["mark_count"] += 1
            programme_map[programme_name]["marks_total"] += mark_value
            programme_map[programme_name]["mark_count"] += 1
            programme_map[programme_name]["level_breakdown"][level_label]["marks_total"] += mark_value
            programme_map[programme_name]["level_breakdown"][level_label]["mark_count"] += 1

            if mark_value >= 50:
                level_map[level_key]["pass_count"] += 1
                level_map[level_key]["programme_breakdown"][programme_name]["pass_count"] += 1
                gender_map[gender_key]["pass_count"] += 1
                programme_map[programme_name]["pass_count"] += 1
                programme_map[programme_name]["level_breakdown"][level_label]["pass_count"] += 1

    level_rows = []
    level_chart_rows = []
    for item in sorted(level_map.values(), key=lambda row: (row["sort_year"], row["sort_semester"])):
        top_programme = ""
        if item["programme_counts"]:
            top_programme = max(item["programme_counts"].items(), key=lambda entry: entry[1])[0]

        mark_count = item["mark_count"]
        avg_mark = round(item["marks_total"] / mark_count) if mark_count else 0
        pass_rate = round((item["pass_count"] / mark_count) * 100) if mark_count else 0
        student_count = len(item["students"])
        programme_breakdown_rows = []
        for programme_breakdown in item["programme_breakdown"].values():
            breakdown_mark_count = programme_breakdown["mark_count"]
            breakdown_average_mark = (
                round(programme_breakdown["marks_total"] / breakdown_mark_count)
                if breakdown_mark_count
                else 0
            )
            breakdown_pass_rate = (
                round((programme_breakdown["pass_count"] / breakdown_mark_count) * 100)
                if breakdown_mark_count
                else 0
            )
            programme_breakdown_rows.append(
                {
                    "programme": programme_breakdown["programme"],
                    "registrations": programme_breakdown["registrations"],
                    "students": len(programme_breakdown["students"]),
                    "average_mark": breakdown_average_mark,
                    "average_mark_display": breakdown_average_mark if breakdown_mark_count else "--",
                    "pass_rate": f"{breakdown_pass_rate}%",
                    "pass_rate_value": breakdown_pass_rate,
                    "results": breakdown_mark_count,
                }
            )

        programme_breakdown_rows.sort(
            key=lambda row: (-row["registrations"], -row["average_mark"], -row["pass_rate_value"], row["programme"])
        )

        level_rows.append(
            {
                "level": item["level"],
                "students": student_count,
                "registrations": item["registrations"],
                "average_mark": avg_mark,
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
                "below_target": pass_rate < ACADEMIC_LEVEL_PASS_TARGET,
                "top_programme": top_programme,
            }
        )
        level_chart_rows.append(
            {
                "level": item["level"],
                "students": student_count,
                "registrations": item["registrations"],
                "average_mark": avg_mark,
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
                "top_programme": top_programme,
                "male_count": len(item["gender_students"]["male"]),
                "female_count": len(item["gender_students"]["female"]),
                "unspecified_count": len(item["gender_students"]["unspecified"]),
                "programme_breakdown": programme_breakdown_rows,
            }
        )

    total_students = len({student_id for data in gender_map.values() for student_id in data["students"]})
    gender_performance_rows = []
    for key, label in GENDER_BUCKETS:
        item = gender_map[key]
        student_count = len(item["students"])
        mark_count = item["mark_count"]
        avg_mark = round(item["marks_total"] / mark_count) if mark_count else 0
        pass_rate = round((item["pass_count"] / mark_count) * 100) if mark_count else 0
        student_share = round((student_count / total_students) * 100) if total_students else 0

        gender_performance_rows.append(
            {
                "key": key,
                "label": label,
                "students": student_count,
                "student_share": f"{student_share}%",
                "student_share_value": student_share,
                "results": mark_count,
                "average_mark": avg_mark,
                "average_mark_display": avg_mark if mark_count else "--",
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
            }
        )

    programme_performance_rows = []
    for programme_name, item in programme_map.items():
        mark_count = item["mark_count"]
        avg_mark = round(item["marks_total"] / mark_count) if mark_count else 0
        pass_rate = round((item["pass_count"] / mark_count) * 100) if mark_count else 0
        lead_level = (
            max(item["level_counts"].items(), key=lambda entry: (entry[1], entry[0]))[0]
            if item["level_counts"]
            else ""
        )
        level_breakdown_rows = []
        for breakdown in sorted(
            item["level_breakdown"].values(),
            key=lambda row: (row["sort_year"], row["sort_semester"]),
        ):
            breakdown_mark_count = breakdown["mark_count"]
            breakdown_average_mark = (
                round(breakdown["marks_total"] / breakdown_mark_count)
                if breakdown_mark_count
                else 0
            )
            breakdown_pass_rate = (
                round((breakdown["pass_count"] / breakdown_mark_count) * 100)
                if breakdown_mark_count
                else 0
            )
            level_breakdown_rows.append(
                {
                    "level": breakdown["level"],
                    "registrations": breakdown["registrations"],
                    "students": len(breakdown["students"]),
                    "average_mark": breakdown_average_mark,
                    "average_mark_display": breakdown_average_mark if breakdown_mark_count else "--",
                    "pass_rate": f"{breakdown_pass_rate}%",
                    "pass_rate_value": breakdown_pass_rate,
                }
            )

        programme_performance_rows.append(
            {
                "programme": programme_name,
                "students": len(item["students"]),
                "registrations": item["registrations"],
                "average_mark": avg_mark,
                "average_mark_display": avg_mark if mark_count else "--",
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
                "lead_level": lead_level,
                "level_breakdown": level_breakdown_rows,
            }
        )

    programme_performance_rows.sort(
        key=lambda row: (-row["pass_rate_value"], -row["average_mark"], -row["registrations"], row["programme"])
    )

    return {
        "level_rows": level_rows,
        "level_chart_rows": level_chart_rows,
        "gender_performance_rows": gender_performance_rows,
        "programme_performance_rows": programme_performance_rows,
    }


def build_academic_level_summary_snapshot(request, search_query=""):
    """Build a lightweight summary snapshot without the full chart payload structures."""

    registrations = list(get_academic_level_registrations(request, search_query))
    registration_level_index = build_registration_display_level_index_for_student_ids(
        {registration.student_id for registration in registrations},
        faculty_name=request.GET.get("faculty", "").strip(),
    ) or build_registration_display_level_index(registrations)
    level_summary = {}
    programme_summary = {}
    gender_summary = {
        key: {
            "label": label,
            "students": set(),
            "marks_total": 0,
            "mark_count": 0,
            "pass_count": 0,
        }
        for key, label in GENDER_BUCKETS
    }

    for registration in registrations:
        level_meta = registration_level_index.get(registration.id)
        if level_meta:
            year = level_meta["display_year"]
            semester = level_meta["display_semester"]
            level_label = level_meta["academic_level_label"]
        else:
            year, semester = extract_registration_year_semester(registration)
            level_label = f"Year {year} Semester {semester}"
        level_key = f"{year}.{semester}"
        gender_key = normalize_gender_key(registration.student.gender)
        programme_name = registration.programme.normalized_name

        if level_key not in level_summary:
            level_summary[level_key] = {
                "level": level_label,
                "sort_year": int(year) if str(year).isdigit() else 0,
                "sort_semester": int(semester) if str(semester).isdigit() else 0,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
            }

        if programme_name not in programme_summary:
            programme_summary[programme_name] = {
                "programme": programme_name,
                "registrations": 0,
            }

        level_summary[level_key]["registrations"] += 1
        level_summary[level_key]["students"].add(registration.student_id)
        programme_summary[programme_name]["registrations"] += 1
        gender_summary[gender_key]["students"].add(registration.student_id)

        for result in registration.prefetched_course_results:
            if result.mark is None:
                continue

            mark_value = float(result.mark)
            level_summary[level_key]["marks_total"] += mark_value
            level_summary[level_key]["mark_count"] += 1
            gender_summary[gender_key]["marks_total"] += mark_value
            gender_summary[gender_key]["mark_count"] += 1

            if mark_value >= 50:
                level_summary[level_key]["pass_count"] += 1
                gender_summary[gender_key]["pass_count"] += 1

    level_rows = []
    for item in sorted(level_summary.values(), key=lambda row: (row["sort_year"], row["sort_semester"])):
        mark_count = item["mark_count"]
        avg_mark = round(item["marks_total"] / mark_count) if mark_count else 0
        pass_rate = round((item["pass_count"] / mark_count) * 100) if mark_count else 0
        level_rows.append(
            {
                "level": item["level"],
                "students": len(item["students"]),
                "registrations": item["registrations"],
                "average_mark": avg_mark,
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
            }
        )

    total_students = len({student_id for item in gender_summary.values() for student_id in item["students"]})
    gender_rows = []
    for key, label in GENDER_BUCKETS:
        item = gender_summary[key]
        student_count = len(item["students"])
        student_share = round((student_count / total_students) * 100) if total_students else 0
        gender_rows.append(
            {
                "key": key,
                "label": label,
                "students": student_count,
                "student_share": f"{student_share}%",
                "student_share_value": student_share,
            }
        )

    programme_rows = sorted(
        programme_summary.values(),
        key=lambda row: (-row["registrations"], row["programme"]),
    )

    return {
        "metrics": {
            "levels": len(level_summary),
            "registrations": sum(item["registrations"] for item in level_summary.values()),
            "students": sum(len(item["students"]) for item in level_summary.values()),
            "average_pass_rate": (
                f"{round(sum(round((item['pass_count'] / item['mark_count']) * 100) for item in level_summary.values() if item['mark_count']) / len(level_summary))}%"
                if level_summary
                else "0%"
            ),
        },
        "story_payload": {
            "level_rows": level_rows,
            "gender_rows": gender_rows,
            "programme_rows": programme_rows,
        },
    }


def get_academic_level_summary_values(request, search_query="", academic_level_data=None):
    """Calculate academic-level summary metrics for asynchronous loading."""

    if academic_level_data is not None:
        level_rows = academic_level_data["level_rows"]
        return {
            "levels": len(level_rows),
            "registrations": sum(row["registrations"] for row in level_rows),
            "students": sum(row["students"] for row in level_rows),
            "average_pass_rate": (
                f"{round(sum(int(row['pass_rate'].replace('%', '')) for row in level_rows) / len(level_rows))}%"
                if level_rows
                else "0%"
            ),
        }

    return build_academic_level_summary_snapshot(request, search_query)["metrics"]


def _build_academic_level_cache_key(request, suffix):
    """Create a stable cache key for the current academic-level filter scope."""

    query_string = urlencode(sorted(request.GET.lists()), doseq=True)
    return f"dashboard:academic-level:{suffix}:{query_string or 'all'}"


def get_cached_academic_level_dashboard_data(request, search_query=""):
    """Return cached academic-level analytics for the current filter scope."""

    cache_key = _build_academic_level_cache_key(request, "payload")
    return cache.get_or_set(
        cache_key,
        lambda: build_academic_level_data(request, search_query),
        ACADEMIC_LEVEL_CACHE_TTL_SECONDS,
    )


def get_cached_academic_level_summary_snapshot(request, search_query=""):
    """Return cached academic-level summary metrics and banner snapshot for the current scope."""

    cache_key = _build_academic_level_cache_key(request, "summary")
    return cache.get_or_set(
        cache_key,
        lambda: build_academic_level_summary_snapshot(request, search_query),
        ACADEMIC_LEVEL_CACHE_TTL_SECONDS,
    )


def _academic_level_registration_rows(request, search_query=""):
    """Return filtered registrations annotated with display-level metadata."""

    registrations = list(get_academic_level_registrations(request, search_query))
    student_ids = {registration.student_id for registration in registrations}
    faculty_name = request.GET.get("faculty", "").strip()
    registration_level_index = build_registration_display_level_index_for_student_ids(
        student_ids,
        faculty_name=faculty_name,
    ) or build_registration_display_level_index(registrations)
    cumulative_average_index = _build_registration_cumulative_average_index(student_ids, faculty_name)

    rows = []
    for registration in registrations:
        level_meta = registration_level_index.get(registration.id)
        if level_meta:
            year = level_meta["display_year"]
            semester = level_meta["display_semester"]
            level_label = level_meta["academic_level_label"]
        else:
            year, semester = extract_registration_year_semester(registration)
            level_label = f"Year {year} Semester {semester}"

        marks = [
            float(result.mark)
            for result in getattr(registration, "prefetched_course_results", [])
            if result.mark is not None
        ]
        average_mark = round(sum(marks) / len(marks)) if marks else cumulative_average_index.get(registration.id)
        study_mode = _format_study_mode(registration)

        rows.append(
            {
                "registration": registration,
                "student": registration.student,
                "level": level_label,
                "sort_year": int(year) if str(year).isdigit() else 0,
                "sort_semester": int(semester) if str(semester).isdigit() else 0,
                "programme": registration.programme.normalized_name,
                "department": registration.programme.department.name if registration.programme.department else "Not recorded",
                "faculty": (
                    registration.programme.department.faculty.name
                    if registration.programme.department and registration.programme.department.faculty
                    else "Not recorded"
                ),
                "gender_key": normalize_gender_key(registration.student.gender),
                "gender": registration.student.gender.title() if registration.student.gender else "Unspecified",
                "study_mode": study_mode,
                "average_mark": average_mark,
            }
        )

    return rows


def _format_study_mode(registration):
    raw_value = (
        getattr(registration.attendance_type_record, "name", "")
        or str(registration.attendance_type_id or "").strip()
    )
    normalized = str(raw_value or "").strip().lower()
    if not normalized:
        return "Not recorded"
    if normalized in {"2", "visiting", "visitor", "exchange"} or "visit" in normalized:
        return "Visiting"
    if normalized in {"1", "conventional", "regular", "normal"}:
        return "Conventional"
    return str(raw_value).strip().title()


def _matches_bucket(value, bucket):
    return str(value or "").strip().lower() == str(bucket or "").strip().lower()


def _build_registration_cumulative_average_index(student_ids, faculty_name=""):
    """Map registrations to the cumulative average shown by student detail pages."""

    if not student_ids:
        return {}

    registrations = (
        Registration.objects.filter(student_id__in=student_ids)
        .select_related("student", "programme__department__faculty", "period", "attendance_type_record")
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
        .order_by("student_id", "period__external_id", "id")
    )
    if faculty_name:
        registrations = registrations.filter(programme__department__faculty__name=faculty_name)

    registrations_by_student = {}
    for registration in registrations:
        registrations_by_student.setdefault(registration.student_id, []).append(registration)

    average_index = {}
    for student_registrations in registrations_by_student.values():
        timeline = build_student_timeline(student_registrations)
        latest_results_by_course = {}
        for group in timeline["groups"]:
            for result_row in group["results"]:
                latest_results_by_course[result_row["course_code"]] = result_row

            marks = [
                result_row["mark_value"]
                for result_row in latest_results_by_course.values()
                if result_row["mark_value"] is not None
            ]
            if not marks:
                continue

            average_mark = round(sum(marks) / len(marks))
            for registration in group["registrations"]:
                average_index[registration.id] = average_mark

    return average_index


def _filter_academic_level_drilldown_rows(rows, chart_key, bucket_key):
    parts = [part.strip() for part in str(bucket_key or "").split("|")]

    if chart_key == "level":
        return [row for row in rows if _matches_bucket(row["level"], parts[0] if parts else "")]
    if chart_key == "gender":
        return [row for row in rows if _matches_bucket(row["gender_key"], parts[0] if parts else "")]
    if chart_key == "programme":
        return [row for row in rows if _matches_bucket(row["programme"], parts[0] if parts else "")]
    if chart_key == "level_programme" and len(parts) >= 2:
        return [
            row for row in rows
            if _matches_bucket(row["level"], parts[0]) and _matches_bucket(row["programme"], parts[1])
        ]
    if chart_key == "programme_level" and len(parts) >= 2:
        return [
            row for row in rows
            if _matches_bucket(row["programme"], parts[0]) and _matches_bucket(row["level"], parts[1])
        ]
    if chart_key == "gender_programme" and len(parts) >= 2:
        return [
            row for row in rows
            if _matches_bucket(row["gender_key"], parts[0]) and _matches_bucket(row["programme"], parts[1])
        ]
    if chart_key == "level_gender" and len(parts) >= 2:
        return [
            row for row in rows
            if _matches_bucket(row["level"], parts[0]) and _matches_bucket(row["gender_key"], parts[1])
        ]
    if chart_key == "level_study_mode" and len(parts) >= 2:
        return [
            row for row in rows
            if _matches_bucket(row["level"], parts[0]) and _matches_bucket(row["study_mode"], parts[1])
        ]

    return []


def _display_gender(bucket_key):
    for key, label in GENDER_BUCKETS:
        if key == bucket_key:
            return label
    return str(bucket_key or "Unspecified").title()


def _breadcrumb_items(chart_key, bucket_key):
    parts = [part.strip() for part in str(bucket_key or "").split("|")]
    items = [{"label": "Academic Levels", "chart": "", "bucket": ""}]

    if chart_key == "level" and parts:
        items.append({"label": parts[0], "chart": "level", "bucket": parts[0]})
    elif chart_key == "gender" and parts:
        items.append({"label": _display_gender(parts[0]), "chart": "gender", "bucket": parts[0]})
    elif chart_key == "programme" and parts:
        items.append({"label": parts[0], "chart": "programme", "bucket": parts[0]})
    elif chart_key == "level_programme" and len(parts) >= 2:
        items.extend([
            {"label": parts[0], "chart": "level", "bucket": parts[0]},
            {"label": parts[1], "chart": "level_programme", "bucket": bucket_key},
        ])
    elif chart_key == "programme_level" and len(parts) >= 2:
        items.extend([
            {"label": parts[0], "chart": "programme", "bucket": parts[0]},
            {"label": parts[1], "chart": "programme_level", "bucket": bucket_key},
        ])
    elif chart_key == "gender_programme" and len(parts) >= 2:
        items.extend([
            {"label": _display_gender(parts[0]), "chart": "gender", "bucket": parts[0]},
            {"label": parts[1], "chart": "gender_programme", "bucket": bucket_key},
        ])
    elif chart_key == "level_gender" and len(parts) >= 2:
        items.extend([
            {"label": parts[0], "chart": "level", "bucket": parts[0]},
            {"label": _display_gender(parts[1]), "chart": "level_gender", "bucket": bucket_key},
        ])
    elif chart_key == "level_study_mode" and len(parts) >= 2:
        items.extend([
            {"label": parts[0], "chart": "level", "bucket": parts[0]},
            {"label": parts[1], "chart": "level_study_mode", "bucket": bucket_key},
        ])

    return items


def _drilldown_title(chart_key, bucket_key):
    parts = [part.strip() for part in str(bucket_key or "").split("|")]
    if chart_key == "level" and parts:
        return f"{parts[0]} Drill-Down"
    if chart_key == "gender" and parts:
        return f"{_display_gender(parts[0])} Students"
    if chart_key == "programme" and parts:
        return f"{parts[0]} Drill-Down"
    if len(parts) >= 2:
        return f"{parts[-1]} Students"
    return "Academic Level Drill-Down"


def _build_hierarchy_payload(chart_key, bucket_key, matched_rows):
    parts = [part.strip() for part in str(bucket_key or "").split("|")]

    if chart_key == "level" and parts:
        grouped = {}
        for row in matched_rows:
            item = grouped.setdefault(
                row["programme"],
                {
                    "label": row["programme"],
                    "count": 0,
                    "department": row["department"],
                    "next_chart": "level_programme",
                    "next_bucket": f"{parts[0]}|{row['programme']}",
                },
            )
            item["count"] += 1
        return {
            "type": "programmes",
            "data": sorted(grouped.values(), key=lambda item: (-item["count"], item["label"])),
        }

    if chart_key == "gender" and parts:
        grouped = {}
        for row in matched_rows:
            item = grouped.setdefault(
                row["programme"],
                {
                    "label": row["programme"],
                    "count": 0,
                    "department": row["department"],
                    "next_chart": "gender_programme",
                    "next_bucket": f"{parts[0]}|{row['programme']}",
                },
            )
            item["count"] += 1
        return {
            "type": "programmes",
            "data": sorted(grouped.values(), key=lambda item: (-item["count"], item["label"])),
        }

    if chart_key == "programme" and parts:
        grouped = {}
        for row in matched_rows:
            item = grouped.setdefault(
                row["level"],
                {
                    "label": row["level"],
                    "count": 0,
                    "sort_year": row["sort_year"],
                    "sort_semester": row["sort_semester"],
                    "next_chart": "programme_level",
                    "next_bucket": f"{parts[0]}|{row['level']}",
                },
            )
            item["count"] += 1
        return {
            "type": "levels",
            "data": sorted(grouped.values(), key=lambda item: (item["sort_year"], item["sort_semester"], item["label"])),
        }

    return None


def _build_student_drilldown_payload(request, chart_key, bucket_key, matched_rows, page=1, page_size=10):
    unique_rows = {}
    for row in sorted(
        matched_rows,
        key=lambda item: (item["student"].surname, item["student"].first_names, item["sort_year"], item["sort_semester"]),
    ):
        unique_rows.setdefault(row["student"].registration_number, row)

    paginator = Paginator(list(unique_rows.values()), page_size)
    page_obj = paginator.get_page(page)
    rows = []
    for row in page_obj:
        student = row["student"]
        rows.append(
            {
                "name": student.full_name,
                "registration_number": student.registration_number,
                "academic_level": row["level"],
                "programme": row["programme"],
                "department": row["department"],
                "gender": row["gender"],
                "study_mode": row["study_mode"],
                "average_mark": row["average_mark"] if row["average_mark"] is not None else "--",
                "decision": row["registration"].decision.title().replace(" And ", " & ") if row["registration"].decision else "--",
                "detail_url": reverse("dashboard:student-detail", args=[student.registration_number.lower()]),
            }
        )

    return {
        "type": "students",
        "columns": ACADEMIC_LEVEL_DRILLDOWN_COLUMNS,
        "rows": rows,
        "total_count": paginator.count,
        "page": page_obj.number,
        "page_size": page_size,
        "page_count": paginator.num_pages,
    }


def build_academic_level_drilldown_data(request, chart_key, bucket_key, page=1, page_size=10, search_query=""):
    """Build modal drill-down data for Academic Levels charts."""

    chart_key = str(chart_key or "").strip().lower()
    bucket_key = str(bucket_key or "").strip()
    rows = _academic_level_registration_rows(request, search_query)
    matched_rows = _filter_academic_level_drilldown_rows(rows, chart_key, bucket_key)
    hierarchy_payload = _build_hierarchy_payload(chart_key, bucket_key, matched_rows)
    payload = hierarchy_payload or _build_student_drilldown_payload(
        request,
        chart_key,
        bucket_key,
        matched_rows,
        page=page,
        page_size=page_size,
    )

    payload.update(
        {
            "title": _drilldown_title(chart_key, bucket_key),
            "subtitle": "Filtered by the active dashboard scope.",
            "chart_key": chart_key,
            "bucket_key": bucket_key,
            "breadcrumbs": _breadcrumb_items(chart_key, bucket_key),
        }
    )
    return payload

import re

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.decorators import (
    ajax_login_required,
    is_platform_admin,
    login_required_except_domains,
    platform_admin_required,
)
from accounts.forms import SystemManagementUserForm
from accounts.models import LoginLockout
from .models import AcademicPeriod, CourseResult, Faculty, Programme, Registration, Student

SIDEBAR_ITEMS = [
    {"key": "dashboard", "label": "Dashboard", "url_name": "dashboard:home"},
    {"key": "students", "label": "Students", "url_name": "dashboard:students"},
    {"key": "programmes", "label": "Programmes", "url_name": "dashboard:programme"},
    {"key": "demographics", "label": "Demographics", "url_name": "dashboard:demographic"},
    {"key": "academic-levels", "label": "Academic Levels", "url_name": "dashboard:academic-level"},
    {"key": "risk", "label": "Risk", "url_name": "dashboard:risk"},
    {"key": "insights", "label": "Insights", "url_name": "dashboard:insights"},
    {"key": "system-management", "label": "System Management", "url_name": "dashboard:system-management", "requires_admin": True},
]

HOME_SUMMARY_CARD_SPECS = [
    {"key": "enrolled", "label": "Enrolled", "tone": "default"},
    {"key": "registered", "label": "Registered", "tone": "default"},
    {"key": "pass_rate", "label": "Pass Rate", "tone": "default"},
    {"key": "completion_rate", "label": "Completion Rate", "tone": "danger"},
    {"key": "on_time_graduation", "label": "On-Time Graduation", "tone": "default"},
    {"key": "average_mark", "label": "Average Mark", "tone": "default"},
    {"key": "first_semester", "label": "First Semester", "tone": "default"},
    {"key": "at_risk", "label": "At Risk", "tone": "default"},
]
PROGRAMME_SUMMARY_CARD_SPECS = [
    {"key": "programmes", "label": "Programmes", "tone": "default"},
    {"key": "registrations", "label": "Registrations", "tone": "default"},
    {"key": "students", "label": "Students", "tone": "default"},
    {"key": "average_pass_rate", "label": "Average Pass Rate", "tone": "default"},
]
DEMOGRAPHIC_SUMMARY_CARD_SPECS = [
    {"key": "students", "label": "Students", "tone": "default"},
    {"key": "male", "label": "Male", "tone": "default"},
    {"key": "female", "label": "Female", "tone": "default"},
    {"key": "birth_locations", "label": "Birth Locations", "tone": "default"},
]
ACADEMIC_LEVEL_SUMMARY_CARD_SPECS = [
    {"key": "levels", "label": "Levels", "tone": "default"},
    {"key": "registrations", "label": "Registrations", "tone": "default"},
    {"key": "students", "label": "Students", "tone": "default"},
    {"key": "average_pass_rate", "label": "Average Pass Rate", "tone": "default"},
]
RISK_SUMMARY_CARD_SPECS = [
    {"key": "at_risk_students", "label": "At Risk Students", "tone": "danger"},
    {"key": "high_risk", "label": "High Risk", "tone": "danger"},
    {"key": "medium_risk", "label": "Medium Risk", "tone": "default"},
    {"key": "multi_fail", "label": "2+ Failed Modules", "tone": "default"},
]
SYSTEM_MANAGEMENT_SUMMARY_CARD_SPECS = [
    {"key": "total_users", "label": "Users", "tone": "default"},
    {"key": "active_users", "label": "Active Accounts", "tone": "default"},
    {"key": "administrators", "label": "Administrators", "tone": "default"},
    {"key": "locked_accounts", "label": "Locked Accounts", "tone": "danger"},
]
RETENTION_EXIT_DECISIONS = {
    "excluded",
    "withdrawn",
    "dropped",
    "dropout",
    "suspended",
    "stopped",
    "fail",
    "failed",
}
HIGH_RISK_DECISIONS = {
    "retake",
    "repeat",
    "fail",
    "failed",
    "excluded",
    "withdrawn",
    "dropped",
    "dropout",
    "suspended",
    "stopped",
}
RISK_PRIORITY = {"High Risk": 0, "Medium Risk": 1, "Low Risk": 2}


def extract_period_year(period_name):
    """Extract a four-digit year from an academic period label."""

    match = re.search(r"(20\d{2})", period_name or "")
    return match.group(1) if match else ""


def format_period_label(period_name):
    """Normalize a period label for filter display."""

    if not period_name:
        return ""
    text = re.sub(r"\b20\d{2}\b", "", period_name, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text.replace("-", " - ")).strip(" -")
    return text.title()


def format_academic_year_label(academic_year):
    """Convert a raw academic year value into a user-friendly year label."""

    text = str(academic_year or "").strip()
    if not text:
        return "Year"
    if text.lower().startswith("year "):
        return text.title()
    return f"Year {text}"


def format_semester_label(semester):
    """Convert a semester value into a user-friendly semester label."""

    text = str(semester or "").strip()
    if not text:
        return "Semester"

    normalized = text.lower()
    if normalized in {"1", "one", "first"}:
        return "Semester 1"
    if normalized in {"2", "two", "second"}:
        return "Semester 2"
    if normalized.startswith("semester "):
        return text.title()
    if text.isdigit():
        return f"Semester {text}"
    return text.title()


def format_academic_level_label(academic_year, semester):
    """Combine academic year and semester into a university-friendly level label."""

    year_label = format_academic_year_label(academic_year)
    semester_label = format_semester_label(semester)
    return f"{year_label}, {semester_label}"


def build_filters(request):
    """Build shared topbar filter metadata from request query parameters."""

    selected_year = request.GET.get("year", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_faculty = request.GET.get("faculty", "").strip()

    periods = list(AcademicPeriod.objects.order_by("name").values("name"))
    years = sorted({extract_period_year(period["name"]) for period in periods if extract_period_year(period["name"])}, reverse=True)
    period_options = sorted({format_period_label(period["name"]) for period in periods if format_period_label(period["name"])})
    faculty_options = list(Faculty.objects.order_by("name").values_list("name", flat=True))

    return {
        "selected_year": selected_year,
        "selected_period": selected_period,
        "selected_faculty": selected_faculty,
        "filters": [
            {"label": "Year", "name": "year", "selected": selected_year, "options": years, "all_label": "All"},
            {"label": "Period", "name": "period", "selected": selected_period, "options": period_options, "all_label": "All"},
            {"label": "Faculty", "name": "faculty", "selected": selected_faculty, "options": faculty_options, "all_label": "All"},
        ],
    }


def build_layout_context(request, active_key):
    """Build shared sidebar and filter context for dashboard templates."""

    items = []
    for item in SIDEBAR_ITEMS:
        items.append(
            {
                **item,
                "is_active": item["key"] == active_key,
            }
        )

    context = build_filters(request)
    context.update({
        "sidebar_items": items,
    })
    return context


def get_active_user_lockout_records():
    """Return active identifier-based lockouts keyed by normalized email/identifier."""

    records = {}
    active_lockouts = (
        LoginLockout.objects.filter(is_locked=True, locked_until__gt=timezone.now())
        .exclude(identifier="")
        .order_by("identifier", "-locked_until")
    )
    for record in active_lockouts:
        key = record.identifier.lower()
        if key not in records:
            records[key] = record
    return records


def get_system_management_summary_values():
    """Calculate top-level user and access-control metrics for the system page."""

    user_model = get_user_model()
    users = user_model.objects.select_related("user_type")
    active_lockouts = get_active_user_lockout_records()

    return {
        "total_users": users.count(),
        "active_users": users.filter(is_active=True).count(),
        "administrators": users.filter(Q(is_superuser=True) | Q(is_staff=True) | Q(user_type__code="admin")).distinct().count(),
        "locked_accounts": len(active_lockouts),
    }


def build_system_user_rows(users, lockout_records, current_user):
    """Transform managed users into template rows with status and action metadata."""

    rows = []
    for user in users:
        lockout = lockout_records.get(user.email.lower())
        rows.append(
            {
                "id": user.id,
                "name": user.get_full_name() or "Not provided",
                "email": user.email,
                "role": user.user_type.name if user.user_type else "No role",
                "role_code": getattr(user.user_type, "code", ""),
                "is_active": user.is_active,
                "is_staff": user.is_staff or user.is_superuser,
                "is_superuser": user.is_superuser,
                "status_label": "Active" if user.is_active else "Inactive",
                "joined": timezone.localtime(user.date_joined).strftime("%d %b %Y"),
                "last_login": timezone.localtime(user.last_login).strftime("%d %b %Y %H:%M") if user.last_login else "Never",
                "lockout_label": (
                    f"Locked until {timezone.localtime(lockout.locked_until).strftime('%d %b %H:%M')}"
                    if lockout and lockout.locked_until
                    else "Clear"
                ),
                "has_lockout": bool(lockout),
                "can_toggle_active": user.pk != current_user.pk,
                "is_self": user.pk == current_user.pk,
            }
        )
    return rows


def build_summary_cards(specs, values=None):
    """Build summary card payloads for initial render or hydrated responses."""

    values = values or {}
    return [
        {
            "key": spec["key"],
            "label": spec["label"],
            "tone": spec.get("tone", "default"),
            "value": values.get(spec["key"], "--"),
        }
        for spec in specs
    ]


def build_registration_filter_q(request, prefix=""):
    """Build a reusable registration filter for querysets and annotations."""

    selected_year = request.GET.get("year", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_faculty = request.GET.get("faculty", "").strip()

    filters = Q()
    if selected_year:
        filters &= Q(**{f"{prefix}period__name__icontains": selected_year})
    if selected_period:
        filters &= Q(**{f"{prefix}period__name__icontains": selected_period})
    if selected_faculty:
        filters &= Q(**{f"{prefix}programme__department__faculty__name": selected_faculty})

    return filters


def get_filtered_registrations(request):
    """Return registrations filtered by the active year, period, and faculty."""

    registrations = (
        Registration.objects.select_related(
            "student",
            "programme__department__faculty",
            "period",
        )
        .prefetch_related("course_results")
        .order_by("student__surname", "student__first_names")
    )

    return registrations.filter(build_registration_filter_q(request))


def get_filtered_results(registrations):
    """Return non-null course results limited to a filtered registration queryset."""

    return CourseResult.objects.filter(registration__in=registrations).exclude(mark__isnull=True)


def get_home_summary_values(request):
    """Calculate overview metrics for the home dashboard asynchronously."""

    registrations = get_filtered_registrations(request)
    filtered_results = get_filtered_results(registrations)

    total_registered = registrations.count()
    total_students = registrations.values("student_id").distinct().count()
    pass_count = filtered_results.filter(mark__gte=50).count()
    result_count = filtered_results.count()
    completion_rate = registrations.filter(decision__iexact="PROCEED").count()
    avg_mark = filtered_results.aggregate(value=Avg("mark"))["value"]
    first_year_retention = registrations.filter(period__semester="1").count()
    on_time_graduation = registrations.filter(decision__iexact="PROCEED", carrying=0).count()
    at_risk_count = (
        filtered_results.filter(mark__lt=50)
        .values("registration__student_id")
        .annotate(fail_count=Count("id"))
        .filter(fail_count__gte=2)
        .count()
    )

    return {
        "enrolled": total_students,
        "registered": total_registered,
        "pass_rate": f"{round((pass_count / result_count) * 100)}%" if result_count else "0%",
        "completion_rate": completion_rate,
        "on_time_graduation": on_time_graduation,
        "average_mark": round(avg_mark or 0),
        "first_semester": first_year_retention,
        "at_risk": at_risk_count,
    }


def get_programmes_queryset(request, search_query=""):
    """Return annotated programme rows for programme analytics pages."""

    programme_filter = build_registration_filter_q(request, prefix="registrations__")
    programmes = (
        Programme.objects.select_related("department__faculty")
        .filter(programme_filter)
        .annotate(
            registration_count=Count("registrations", filter=programme_filter, distinct=True),
            student_count=Count("registrations__student", filter=programme_filter, distinct=True),
            average_mark=Avg(
                "registrations__course_results__mark",
                filter=programme_filter & Q(registrations__course_results__mark__isnull=False),
            ),
            pass_count=Count(
                "registrations__course_results",
                filter=programme_filter & Q(registrations__course_results__mark__gte=50),
                distinct=True,
            ),
            mark_count=Count(
                "registrations__course_results",
                filter=programme_filter & Q(registrations__course_results__mark__isnull=False),
                distinct=True,
            ),
        )
        .distinct()
        .order_by("name")
    )

    if search_query:
        programmes = programmes.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(department__name__icontains=search_query)
            | Q(department__faculty__name__icontains=search_query)
        )

    return programmes


def build_programme_rows(programmes):
    """Transform annotated programme queryset rows for template rendering."""

    programme_rows = []
    for programme in programmes:
        pass_rate = round((programme.pass_count / programme.mark_count) * 100) if programme.mark_count else 0
        programme_rows.append(
            {
                "code": programme.code,
                "name": programme.name,
                "faculty": programme.department.faculty.name if programme.department else "",
                "department": programme.department.name if programme.department else "",
                "students": programme.student_count,
                "registrations": programme.registration_count,
                "average_mark": round(programme.average_mark or 0),
                "pass_rate": f"{pass_rate}%",
            }
        )

    return programme_rows


def get_programme_summary_values(request, search_query=""):
    """Calculate programme summary metrics for asynchronous loading."""

    programme_rows = build_programme_rows(get_programmes_queryset(request, search_query))

    return {
        "programmes": len(programme_rows),
        "registrations": sum(row["registrations"] for row in programme_rows),
        "students": sum(row["students"] for row in programme_rows),
        "average_pass_rate": (
            f"{round(sum(int(row['pass_rate'].replace('%', '')) for row in programme_rows) / len(programme_rows))}%"
            if programme_rows
            else "0%"
        ),
    }


def build_demographic_data(request, search_query=""):
    """Build demographic tables and supporting counts from filtered registrations."""

    registrations = get_filtered_registrations(request)
    if search_query:
        registrations = registrations.filter(
            Q(student__first_names__icontains=search_query)
            | Q(student__surname__icontains=search_query)
            | Q(student__gender__icontains=search_query)
            | Q(student__place_of_birth__icontains=search_query)
            | Q(programme__name__icontains=search_query)
        )

    unique_students = {}
    for registration in registrations:
        unique_students[registration.student.registration_number] = {
            "student": registration.student,
            "programme": registration.programme,
        }

    student_values = list(unique_students.values())
    total_students = len(student_values)
    male_count = sum(1 for item in student_values if item["student"].gender.upper() == "MALE")
    female_count = sum(1 for item in student_values if item["student"].gender.upper() == "FEMALE")
    unspecified_count = total_students - male_count - female_count

    gender_rows = [
        {"label": "Male", "count": male_count, "share": f"{round((male_count / total_students) * 100) if total_students else 0}%"},
        {"label": "Female", "count": female_count, "share": f"{round((female_count / total_students) * 100) if total_students else 0}%"},
        {"label": "Unspecified", "count": unspecified_count, "share": f"{round((unspecified_count / total_students) * 100) if total_students else 0}%"},
    ]

    location_counts = {}
    programme_gender_counts = {}
    for item in student_values:
        place = item["student"].place_of_birth.strip() or "Unspecified"
        location_counts[place] = location_counts.get(place, 0) + 1

        programme_name = item["programme"].name
        if programme_name not in programme_gender_counts:
            programme_gender_counts[programme_name] = {"male": 0, "female": 0, "unspecified": 0}

        gender_key = item["student"].gender.strip().lower()
        if gender_key == "male":
            programme_gender_counts[programme_name]["male"] += 1
        elif gender_key == "female":
            programme_gender_counts[programme_name]["female"] += 1
        else:
            programme_gender_counts[programme_name]["unspecified"] += 1

    location_rows = [
        {"place": place, "count": count, "share": f"{round((count / total_students) * 100) if total_students else 0}%"}
        for place, count in sorted(location_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]

    programme_rows = [
        {
            "programme": programme_name,
            "male": counts["male"],
            "female": counts["female"],
            "unspecified": counts["unspecified"],
            "total": counts["male"] + counts["female"] + counts["unspecified"],
        }
        for programme_name, counts in sorted(
            programme_gender_counts.items(),
            key=lambda item: (-(item[1]["male"] + item[1]["female"] + item[1]["unspecified"]), item[0]),
        )[:12]
    ]

    return {
        "total_students": total_students,
        "male_count": male_count,
        "female_count": female_count,
        "location_counts": location_counts,
        "gender_rows": gender_rows,
        "location_rows": location_rows,
        "programme_rows": programme_rows,
    }


def get_demographic_summary_values(request, search_query=""):
    """Calculate demographic summary metrics for asynchronous loading."""

    demographic_data = build_demographic_data(request, search_query)
    return {
        "students": demographic_data["total_students"],
        "male": demographic_data["male_count"],
        "female": demographic_data["female_count"],
        "birth_locations": len(demographic_data["location_counts"]),
    }


def build_academic_level_rows(request, search_query=""):
    """Build academic-level table rows from filtered registrations."""

    registrations = get_filtered_registrations(request)
    if search_query:
        registrations = registrations.filter(
            Q(period__academic_year__icontains=search_query)
            | Q(period__semester__icontains=search_query)
            | Q(programme__name__icontains=search_query)
            | Q(programme__department__name__icontains=search_query)
        )

    level_map = {}
    for registration in registrations:
        year = registration.period.academic_year or "?"
        semester = registration.period.semester or "?"
        level_key = f"{year}.{semester}"

        if level_key not in level_map:
            level_map[level_key] = {
                "level": format_academic_level_label(year, semester),
                "sort_year": int(year) if str(year).isdigit() else 0,
                "sort_semester": int(semester) if str(semester).isdigit() else 0,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
                "programme_counts": {},
            }

        level_map[level_key]["registrations"] += 1
        level_map[level_key]["students"].add(registration.student_id)
        programme_name = registration.programme.name
        level_map[level_key]["programme_counts"][programme_name] = level_map[level_key]["programme_counts"].get(programme_name, 0) + 1

        for result in registration.course_results.all():
            if result.mark is None:
                continue
            level_map[level_key]["marks_total"] += float(result.mark)
            level_map[level_key]["mark_count"] += 1
            if result.mark >= 50:
                level_map[level_key]["pass_count"] += 1

    level_rows = []
    for item in sorted(level_map.values(), key=lambda row: (row["sort_year"], row["sort_semester"])):
        top_programme = ""
        if item["programme_counts"]:
            top_programme = max(item["programme_counts"].items(), key=lambda entry: entry[1])[0]

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
                "top_programme": top_programme,
            }
        )

    return level_rows


def get_academic_level_summary_values(request, search_query=""):
    """Calculate academic-level summary metrics for asynchronous loading."""

    level_rows = build_academic_level_rows(request, search_query)
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


def normalize_decision_label(decision):
    """Normalize a registration decision value for consistent user-facing display."""

    text = str(decision or "").strip()
    return text.title() if text else "Not Recorded"


def build_initials(name):
    """Build a compact avatar label from a student's full name."""

    parts = [part for part in re.split(r"\s+", str(name or "").strip()) if part]
    if not parts:
        return "NA"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def assess_student_risk(registrations):
    """Score a student's filtered registrations and classify their current academic risk."""

    latest_registration = max(registrations, key=lambda registration: (registration.period.external_id, registration.id))
    mark_values = []
    failed_courses = 0

    for registration in registrations:
        for result in registration.course_results.all():
            if result.mark is None:
                continue
            mark_value = float(result.mark)
            mark_values.append(mark_value)
            if mark_value < 50:
                failed_courses += 1

    average_mark = round(sum(mark_values) / len(mark_values)) if mark_values else None
    carrying = max((registration.carrying or 0) for registration in registrations)
    decision_label = normalize_decision_label(latest_registration.decision)
    decision_key = decision_label.lower()

    risk_score = 0
    risk_drivers = []

    if average_mark is not None:
        if average_mark < 50:
            risk_score += 3
            risk_drivers.append("average below 50%")
        elif average_mark < 60:
            risk_score += 1
            risk_drivers.append("average below 60%")

    if failed_courses >= 3:
        risk_score += 3
        risk_drivers.append("3+ failed modules")
    elif failed_courses == 2:
        risk_score += 2
        risk_drivers.append("2 failed modules")
    elif failed_courses == 1:
        risk_score += 1
        risk_drivers.append("1 failed module")

    if carrying >= 2:
        risk_score += 2
        risk_drivers.append(f"{carrying} carried modules")
    elif carrying == 1:
        risk_score += 1
        risk_drivers.append("1 carried module")

    if decision_key in HIGH_RISK_DECISIONS:
        risk_score += 2
        risk_drivers.append(f"{decision_label} decision")

    if risk_score >= 4:
        risk_level = "High Risk"
    elif risk_score >= 2:
        risk_level = "Medium Risk"
    else:
        risk_level = "Low Risk"

    return {
        "latest_registration": latest_registration,
        "average_mark": average_mark,
        "failed_courses": failed_courses,
        "carrying": carrying,
        "risk_score": risk_score,
        "decision": decision_label,
        "risk_level": risk_level,
        "risk_level_key": risk_level.lower().replace(" ", "-"),
        "risk_drivers": ", ".join(risk_drivers) if risk_drivers else "Performance currently stable",
    }


def build_student_risk_profiles(request, search_query=""):
    """Build per-student risk profiles from the currently filtered registration scope."""

    registrations = get_filtered_registrations(request)
    if search_query:
        registrations = registrations.filter(
            Q(student__first_names__icontains=search_query)
            | Q(student__surname__icontains=search_query)
            | Q(student__registration_number__icontains=search_query)
            | Q(programme__name__icontains=search_query)
            | Q(programme__department__name__icontains=search_query)
            | Q(decision__icontains=search_query)
        )

    student_registrations = {}
    for registration in registrations:
        student_registrations.setdefault(registration.student_id, []).append(registration)

    risk_rows = []
    for grouped_registrations in student_registrations.values():
        assessment = assess_student_risk(grouped_registrations)
        if assessment["risk_level"] == "Low Risk":
            continue

        latest_registration = assessment["latest_registration"]
        risk_rows.append(
            {
                "name": latest_registration.student.full_name,
                "registration_number": latest_registration.student.registration_number,
                "programme": latest_registration.programme.name,
                "faculty": (
                    latest_registration.programme.department.faculty.name
                    if latest_registration.programme.department and latest_registration.programme.department.faculty
                    else "Unassigned"
                ),
                "academic_level": format_academic_level_label(
                    latest_registration.period.academic_year,
                    latest_registration.period.semester,
                ),
                "average_mark": assessment["average_mark"] if assessment["average_mark"] is not None else "-",
                "average_mark_sort": assessment["average_mark"] if assessment["average_mark"] is not None else 999,
                "failed_courses": assessment["failed_courses"],
                "carrying": assessment["carrying"],
                "risk_score": assessment["risk_score"],
                "decision": assessment["decision"],
                "risk_level": assessment["risk_level"],
                "risk_level_key": assessment["risk_level_key"],
                "risk_drivers": assessment["risk_drivers"],
                "detail_slug": latest_registration.student.registration_number.lower(),
            }
        )

    return sorted(
        risk_rows,
        key=lambda row: (
            RISK_PRIORITY[row["risk_level"]],
            -row["failed_courses"],
            row["average_mark_sort"],
            row["name"],
        ),
    )


def format_risk_monitor_drivers(risk_driver_text):
    """Remove redundant phrases from the risk-monitor explanation shown on the table."""

    drivers = [driver.strip() for driver in str(risk_driver_text or "").split(",") if driver.strip()]
    filtered_drivers = [driver for driver in drivers if driver.lower() != "average below 50%"]

    if filtered_drivers:
        return ", ".join(filtered_drivers)
    if drivers:
        return "Performance needs support"
    return "Performance currently stable"


def format_insight_flagged_meta(risk_driver_text, academic_level):
    """Build concise flagged-student copy for the insights page."""

    cleaned_driver_text = format_risk_monitor_drivers(risk_driver_text)
    lead_text = cleaned_driver_text.split(", ")[0] if cleaned_driver_text else "Performance needs support"

    if academic_level:
        return f"{lead_text} - {academic_level}"
    return lead_text


def build_risk_rows(request, search_query=""):
    """Build risk-monitor rows for students who need academic intervention."""

    risk_rows = []
    for row in build_student_risk_profiles(request, search_query):
        if row["risk_level"] == "Low Risk":
            continue

        risk_rows.append(
            {
                **row,
                "risk_drivers_display": format_risk_monitor_drivers(row["risk_drivers"]),
            }
        )

    return risk_rows


def get_risk_summary_values(request, search_query=""):
    """Calculate student-risk summary metrics for asynchronous hydration."""

    risk_rows = build_risk_rows(request, search_query)
    return {
        "at_risk_students": len(risk_rows),
        "high_risk": sum(1 for row in risk_rows if row["risk_level"] == "High Risk"),
        "medium_risk": sum(1 for row in risk_rows if row["risk_level"] == "Medium Risk"),
        "multi_fail": sum(1 for row in risk_rows if row["failed_courses"] >= 2),
    }


def build_insight_scope_pills(request):
    """Build small scope badges that summarize the active insights filter context."""

    return [
        {"label": "Live analysis", "variant": "live"},
        {"label": request.GET.get("faculty", "").strip() or "All faculties", "variant": "scope"},
        {"label": request.GET.get("period", "").strip() or "All periods", "variant": "scope"},
        {"label": request.GET.get("year", "").strip() or "All years", "variant": "scope"},
    ]


def build_insights_dashboard_data(request):
    """Assemble the live operational signals and recommendation content for Insights."""

    registrations = list(get_filtered_registrations(request))
    total_registrations = len(registrations)
    risk_profiles = build_student_risk_profiles(request)
    at_risk_profiles = [row for row in risk_profiles if row["risk_level"] != "Low Risk"]
    high_risk_profiles = [row for row in at_risk_profiles if row["risk_level"] == "High Risk"]
    medium_risk_profiles = [row for row in at_risk_profiles if row["risk_level"] == "Medium Risk"]
    total_students = len(risk_profiles)

    retained_students = sum(
        1 for row in risk_profiles if row["decision"].lower() not in RETENTION_EXIT_DECISIONS
    )
    retention_rate = round((retained_students / total_students) * 100) if total_students else 0

    faculty_counts = {}
    for registration in registrations:
        faculty_name = (
            registration.programme.department.faculty.name
            if registration.programme.department and registration.programme.department.faculty
            else "Unassigned"
        )
        faculty_counts[faculty_name] = faculty_counts.get(faculty_name, 0) + 1

    sorted_faculties = sorted(faculty_counts.items(), key=lambda item: (-item[1], item[0]))
    top_faculty_name, top_faculty_count = sorted_faculties[0] if sorted_faculties else ("No faculty data", 0)
    faculty_load = round((top_faculty_count / total_registrations) * 100) if total_registrations else 0

    summary_cards = [
        {
            "label": "At-Risk Students",
            "value": f"{len(at_risk_profiles):,}",
            "note": f"{len(high_risk_profiles)} high priority",
            "tone": "danger",
        },
        {
            "label": "Retention Rate",
            "value": f"{retention_rate}%",
            "note": f"{retained_students:,} students persisting",
            "tone": "warning",
        },
        {
            "label": "Faculty Load",
            "value": f"{faculty_load}%",
            "note": top_faculty_name,
            "tone": "neutral",
        },
        {
            "label": "Enrolled Total",
            "value": f"{total_students:,}",
            "note": f"{total_registrations:,} registrations in scope",
            "tone": "success",
        },
    ]

    flagged_students = []
    for row in at_risk_profiles[:4]:
        meta = format_insight_flagged_meta(row["risk_drivers"], row["academic_level"])
        flagged_students.append(
            {
                "initials": build_initials(row["name"]),
                "name": row["name"],
                "meta": meta,
                "risk_level": row["risk_level"],
                "risk_key": row["risk_level_key"],
                "detail_slug": row["detail_slug"],
            }
        )

    faculty_load_rows = []
    faculty_tones = ["cyan", "teal", "amber", "rose"]
    for index, (name, count) in enumerate(sorted_faculties[:4]):
        faculty_load_rows.append(
            {
                "label": name,
                "value": round((count / total_registrations) * 100) if total_registrations else 0,
                "tone": faculty_tones[index % len(faculty_tones)],
            }
        )

    risk_distribution_rows = []
    risk_bands = [
        ("Critical (6+)", lambda score: score >= 6, "critical"),
        ("High (4-5)", lambda score: 4 <= score <= 5, "high"),
        ("Moderate (2-3)", lambda score: 2 <= score <= 3, "moderate"),
        ("Low (0-1)", lambda score: score <= 1, "low"),
    ]
    for label, matcher, tone in risk_bands:
        count = sum(1 for row in risk_profiles if matcher(row["risk_score"]))
        risk_distribution_rows.append(
            {
                "label": label,
                "count": count,
                "percent": round((count / total_students) * 100) if total_students else 0,
                "tone": tone,
            }
        )

    sample_size_factor = min(14, total_students // 35)
    high_signal_factor = min(10, len(high_risk_profiles) * 2)
    concentration_factor = 8 if faculty_load >= 45 else 4
    confidence_rows = [
        {
            "label": "Student flagging",
            "value": min(96, 78 + sample_size_factor + high_signal_factor),
        },
        {
            "label": "Retention outlook",
            "value": min(95, 74 + sample_size_factor + (4 if retention_rate >= 80 else 1)),
        },
        {
            "label": "Faculty balancing",
            "value": min(93, 70 + sample_size_factor + concentration_factor),
        },
        {
            "label": "Intervention targeting",
            "value": min(97, 76 + sample_size_factor + (6 if at_risk_profiles else 0)),
        },
    ]

    risk_by_programme = {}
    for row in at_risk_profiles:
        risk_by_programme[row["programme"]] = risk_by_programme.get(row["programme"], 0) + 1
    top_risk_programme, top_risk_programme_count = max(
        risk_by_programme.items(),
        key=lambda item: item[1],
        default=("the current watchlist", 0),
    )

    recommendations = [
        {
            "title": "Schedule advisor check-ins",
            "description": (
                f"{len(high_risk_profiles)} students are in the high-risk band. Prioritise outreach for those "
                "carrying modules or sitting on retake decisions in the next intervention cycle."
                if high_risk_profiles
                else "No students are currently in the high-risk band. Maintain weekly review of flagged cases to keep the watchlist stable."
            ),
            "priority": "High priority" if high_risk_profiles else "Monitor",
            "priority_key": "high" if high_risk_profiles else "neutral",
            "action_label": "Open risk register",
            "action_url": reverse("dashboard:risk"),
        },
        {
            "title": f"Review {top_faculty_name} load",
            "description": (
                f"{top_faculty_name} currently holds {faculty_load}% of registrations in scope. Rebalance advising, classroom, and support capacity before the next enrolment spike."
                if total_registrations
                else "Registration data is not yet available for the selected scope. Confirm the filter context before taking a load-balancing decision."
            ),
            "priority": "High priority" if faculty_load >= 50 else "Medium priority",
            "priority_key": "high" if faculty_load >= 50 else "medium",
            "action_label": "Review programmes",
            "action_url": reverse("dashboard:programme"),
        },
        {
            "title": "Target progression support",
            "description": (
                f"{top_risk_programme_count} flagged students are concentrated in {top_risk_programme}. A focused support clinic around repeated failures could improve progression."
                if top_risk_programme_count
                else "Current filters show no flagged concentration by programme. Keep academic-level support general until new signals emerge."
            ),
            "priority": "Medium priority",
            "priority_key": "medium",
            "action_label": "Open academic levels",
            "action_url": reverse("dashboard:academic-level"),
        },
    ]

    return {
        "summary_cards": summary_cards,
        "scope_pills": build_insight_scope_pills(request),
        "flagged_students": flagged_students,
        "flagged_total": len(at_risk_profiles),
        "recommendations": recommendations,
        "faculty_load_rows": faculty_load_rows,
        "risk_distribution_rows": risk_distribution_rows,
        "confidence_rows": confidence_rows,
    }


@login_required_except_domains()
def dashboard_home(request):
    """Render the main overview dashboard shown immediately after login."""

    context = build_layout_context(request, "dashboard")
    context.update(
        {
            "page_title": "Overview Dashboard",
            "summary_cards": build_summary_cards(HOME_SUMMARY_CARD_SPECS),
            "chart_panels": [
                {"title": "Pass vs Fail"},
                {"title": "Risk Level Distribution"},
                {"title": "Progress Status"},
            ],
        }
    )
    return render(request, "dashboard/home.html", context)


@login_required_except_domains()
def student_list(request):
    """Render the paginated student directory with shared dashboard filters."""

    search_query = request.GET.get("q", "").strip()
    filtered_registrations = get_filtered_registrations(request)
    registrations = filtered_registrations
    if search_query:
        registrations = registrations.filter(
            Q(student__first_names__icontains=search_query)
            | Q(student__surname__icontains=search_query)
            | Q(student__registration_number__icontains=search_query)
            | Q(programme__name__icontains=search_query)
            | Q(programme__department__name__icontains=search_query)
        )

    average_marks = dict(
        get_filtered_results(filtered_registrations)
        .values("registration__student_id")
        .annotate(value=Avg("mark"))
        .values_list("registration__student_id", "value")
    )
    latest_registrations = list(
        registrations.order_by("student_id", "-period__external_id", "-id").distinct("student_id")
    )

    student_rows = [
        {
            "name": registration.student.full_name,
            "department": registration.programme.department.name if registration.programme.department else "",
            "program": registration.programme.name,
            "average_mark": round(average_marks.get(registration.student_id) or 0),
            "decision": registration.decision.title(),
            "gender": registration.student.gender.title(),
            "detail_slug": registration.student.registration_number.lower(),
        }
        for registration in latest_registrations
    ]

    paginator = Paginator(student_rows, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_window_start = max(page_obj.number - 2, 1)
    page_window_end = min(page_obj.number + 2, paginator.num_pages)

    context = build_layout_context(request, "students")
    context.update(
        {
            "page_title": "Students Dashboard",
            "students": page_obj.object_list,
            "page_obj": page_obj,
            "page_numbers": range(page_window_start, page_window_end + 1),
            "search_query": search_query,
            "total_students": paginator.count,
        }
    )
    return render(request, "dashboard/students.html", context)


@login_required_except_domains()
def student_detail(request, slug):
    """Render a student profile with term tabs and course results."""

    student_record = get_object_or_404(
        Student.objects.prefetch_related(
            "registrations__course_results__course",
            "registrations__programme__department",
            "registrations__period",
        ),
        registration_number__iexact=slug,
    )
    registrations = list(
        student_record.registrations.select_related("programme", "period").order_by("-period__external_id")
    )
    selected_term_id = request.GET.get("term", "").strip()
    latest_registration = registrations[0] if registrations else None
    selected_registration = latest_registration
    if selected_term_id:
        try:
            selected_registration = next(
                registration for registration in registrations if registration.id == int(selected_term_id)
            )
        except (StopIteration, ValueError):
            selected_registration = latest_registration

    average_mark = student_record.registrations.aggregate(value=Avg("course_results__mark"))["value"]

    results = []
    if selected_registration:
        results = [
            {
                "code": result.course.code,
                "course": result.course.name,
                "period": selected_registration.period.external_id,
                "mark": round(result.mark or 0),
            }
            for result in selected_registration.course_results.all()
        ]

    term_tabs = []
    for registration in registrations:
        year_label = format_academic_year_label(registration.period.academic_year)
        semester_label = format_semester_label(registration.period.semester)
        period_label = format_period_label(registration.period.name)
        tab_meta = semester_label
        if period_label and period_label.lower() != semester_label.lower():
            tab_meta = f"{semester_label} - {period_label}"
        term_tabs.append(
            {
                "id": registration.id,
                "label": year_label,
                "period_name": tab_meta,
                "is_active": selected_registration and registration.id == selected_registration.id,
            }
        )

    student = {
        "name": student_record.full_name,
        "student_number": student_record.registration_number,
        "programme": selected_registration.programme.name if selected_registration else "",
        "academic_level": (
            format_academic_level_label(selected_registration.period.academic_year, selected_registration.period.semester)
            if selected_registration
            else ""
        ),
        "term_name": selected_registration.period.name.title() if selected_registration else "",
        "decision": selected_registration.decision.title() if selected_registration else "",
        "gender": student_record.gender.title(),
        "age": "",
        "place_of_birth": student_record.place_of_birth,
        "cumulative_grade": round(average_mark or 0),
        "term_tabs": term_tabs,
        "results": results,
    }

    context = build_layout_context(request, "students")
    context.update(
        {
            "page_title": student["name"],
            "student": student,
        }
    )
    return render(request, "dashboard/student_detail.html", context)


@login_required_except_domains()
def placeholder_section(request, section_name, title):
    """Render a generic placeholder page for sections still under construction."""

    context = build_layout_context(request, section_name)
    context.update(
        {
            "page_title": title,
            "section_title": title,
            "section_name": section_name,
        }
    )
    return render(request, "dashboard/placeholder.html", context)


@login_required_except_domains()
def risk_view(request):
    """Render the risk-monitor workspace for students who need academic intervention."""

    search_query = request.GET.get("q", "").strip()
    risk_rows = build_risk_rows(request, search_query)

    paginator = Paginator(risk_rows, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_window_start = max(page_obj.number - 2, 1)
    page_window_end = min(page_obj.number + 2, paginator.num_pages)

    context = build_layout_context(request, "risk")
    context.update(
        {
            "page_title": "Risk Dashboard",
            "search_query": search_query,
            "summary_cards": build_summary_cards(RISK_SUMMARY_CARD_SPECS),
            "risk_rows": page_obj.object_list,
            "page_obj": page_obj,
            "page_numbers": range(page_window_start, page_window_end + 1),
            "total_students": paginator.count,
        }
    )
    return render(request, "dashboard/risk.html", context)


@login_required_except_domains()
def insights_view(request):
    """Render the institutional insights board with live flagged-student signals."""

    insights_data = build_insights_dashboard_data(request)

    context = build_layout_context(request, "insights")
    context.update(
        {
            "page_title": "Insights Dashboard",
            "insight_summary_cards": insights_data["summary_cards"],
            "insight_scope_pills": insights_data["scope_pills"],
            "flagged_students": insights_data["flagged_students"],
            "flagged_total": insights_data["flagged_total"],
            "recommendations": insights_data["recommendations"],
            "faculty_load_rows": insights_data["faculty_load_rows"],
            "risk_distribution_rows": insights_data["risk_distribution_rows"],
            "confidence_rows": insights_data["confidence_rows"],
        }
    )
    return render(request, "dashboard/insights.html", context)


@login_required_except_domains()
def programme_view(request):
    """Render programme-level analytics, KPIs, and searchable programme rows."""

    search_query = request.GET.get("q", "").strip()
    programme_rows = build_programme_rows(get_programmes_queryset(request, search_query))

    context = build_layout_context(request, "programmes")
    context.update(
        {
            "page_title": "Programme Dashboard",
            "search_query": search_query,
            "summary_cards": build_summary_cards(PROGRAMME_SUMMARY_CARD_SPECS),
            "programme_rows": programme_rows,
        }
    )
    return render(request, "dashboard/programme.html", context)


@login_required_except_domains()
def demographic_view(request):
    """Render gender and place-of-birth demographic summaries and tables."""

    search_query = request.GET.get("q", "").strip()
    demographic_data = build_demographic_data(request, search_query)

    context = build_layout_context(request, "demographics")
    context.update(
        {
            "page_title": "Demographic Dashboard",
            "search_query": search_query,
            "summary_cards": build_summary_cards(DEMOGRAPHIC_SUMMARY_CARD_SPECS),
            "gender_rows": demographic_data["gender_rows"],
            "location_rows": demographic_data["location_rows"],
            "programme_rows": demographic_data["programme_rows"],
        }
    )
    return render(request, "dashboard/demographic.html", context)


@login_required_except_domains()
def academic_level_view(request):
    """Render analytics grouped by academic year and semester level."""

    search_query = request.GET.get("q", "").strip()
    level_rows = build_academic_level_rows(request, search_query)

    context = build_layout_context(request, "academic-levels")
    context.update(
        {
            "page_title": "Academic Level Dashboard",
            "search_query": search_query,
            "summary_cards": build_summary_cards(ACADEMIC_LEVEL_SUMMARY_CARD_SPECS),
            "level_rows": level_rows,
        }
    )
    return render(request, "dashboard/academic_level.html", context)


@platform_admin_required
def system_management_view(request):
    """Render the admin-only system workspace for user access and platform controls."""

    user_model = get_user_model()
    redirect_target = request.POST.get("next") or reverse("dashboard:system-management")
    show_user_modal = False

    if request.method == "POST":
        action = request.POST.get("action", "create-user")

        if action == "create-user":
            user_form = SystemManagementUserForm(request.POST)
            if user_form.is_valid():
                created_user = user_form.save()
                messages.success(request, f"{created_user.email} was added successfully.")
                return redirect(redirect_target)
            messages.error(request, "Please correct the highlighted user details and try again.")
            show_user_modal = True
        else:
            managed_user = get_object_or_404(user_model, pk=request.POST.get("user_id"))

            if action == "toggle-active":
                if managed_user.pk == request.user.pk and managed_user.is_active:
                    messages.error(request, "You cannot deactivate the account you are currently using.")
                else:
                    managed_user.is_active = not managed_user.is_active
                    managed_user.save(update_fields=["is_active"])
                    state = "activated" if managed_user.is_active else "deactivated"
                    messages.success(request, f"{managed_user.email} was {state}.")
                    return redirect(redirect_target)

            elif action == "clear-lockout":
                updated = LoginLockout.objects.filter(
                    identifier__iexact=managed_user.email,
                    is_locked=True,
                ).update(
                    attempt_count=0,
                    is_locked=False,
                    locked_at=None,
                    locked_until=None,
                )
                if updated:
                    messages.success(request, f"Lockout cleared for {managed_user.email}.")
                else:
                    messages.info(request, f"{managed_user.email} has no active user-specific lockout.")
                return redirect(redirect_target)

            user_form = SystemManagementUserForm(initial={"is_active": True})
    else:
        user_form = SystemManagementUserForm(initial={"is_active": True})

    search_query = request.GET.get("q", "").strip()
    managed_users = user_model.objects.select_related("user_type").order_by("-date_joined", "email")
    if search_query:
        managed_users = managed_users.filter(
            Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(user_type__name__icontains=search_query)
        )

    lockout_records = get_active_user_lockout_records()
    user_rows = build_system_user_rows(managed_users, lockout_records, request.user)

    paginator = Paginator(user_rows, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_window_start = max(page_obj.number - 2, 1)
    page_window_end = min(page_obj.number + 2, paginator.num_pages)

    context = build_layout_context(request, "system-management")
    context.update(
        {
            "page_title": "System Management",
            "hide_filters": True,
            "topbar_kicker": "Platform Administration",
            "topbar_heading": "System Management",
            "summary_cards": build_summary_cards(
                SYSTEM_MANAGEMENT_SUMMARY_CARD_SPECS,
                get_system_management_summary_values(),
            ),
            "user_form": user_form,
            "users": page_obj.object_list,
            "page_obj": page_obj,
            "page_numbers": range(page_window_start, page_window_end + 1),
            "search_query": search_query,
            "current_path": request.get_full_path(),
            "show_user_modal": show_user_modal,
        }
    )
    return render(request, "dashboard/system_management.html", context)


@ajax_login_required
@require_GET
def dashboard_home_metrics(request):
    """Return overview dashboard metrics as JSON for asynchronous hydration."""

    return JsonResponse({"metrics": get_home_summary_values(request)})


@ajax_login_required
@require_GET
def programme_metrics(request):
    """Return programme dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_programme_summary_values(request, search_query)})


@ajax_login_required
@require_GET
def demographic_metrics(request):
    """Return demographic dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_demographic_summary_values(request, search_query)})


@ajax_login_required
@require_GET
def academic_level_metrics(request):
    """Return academic-level dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_academic_level_summary_values(request, search_query)})


@ajax_login_required
@require_GET
def risk_metrics(request):
    """Return student-risk dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_risk_summary_values(request, search_query)})

import re

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Avg, CharField, Count, FloatField, OuterRef, Q, Subquery
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
    {"key": "completion", "label": "Completion Analysis", "url_name": "dashboard:completion"},
    {"key": "graduation", "label": "Graduation Analysis", "url_name": "dashboard:graduation"},
    {"key": "risk", "label": "Risk Analysis", "url_name": "dashboard:risk"},
    {"key": "insights", "label": "Insights", "url_name": "dashboard:insights"},
    {"key": "system-management", "label": "System Management", "url_name": "dashboard:system-management", "requires_admin": True},
]

HOME_SUMMARY_CARD_SPECS = [
    {"key": "enrolled", "label": "Enrolled", "tone": "default"},
    {"key": "registered", "label": "Registered", "tone": "default"},
    {"key": "pass_rate", "label": "Pass Rate", "tone": "default"},
    {"key": "completion_rate", "label": "Completion Rate", "tone": "danger"},
    {"key": "on_time_graduation", "label": "On-Time Graduation", "tone": "default"},
    {"key": "first_year_retention", "label": "First Year Retention", "tone": "default"},
    {"key": "students_satisfaction", "label": "Students Satisfaction", "tone": "default"},
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
GENDER_BUCKETS = (
    ("male", "Male"),
    ("female", "Female"),
    ("unspecified", "Unspecified"),
)


def extract_period_year(period_name):
    """Extract a four-digit year from an academic period label."""

    match = re.search(r"(20\d{2})", period_name or "")
    return match.group(1) if match else ""


def format_period_label(period_name):
    """Normalize a period label for filter display."""

    if not period_name:
        return ""
    
    # Extract year & remove it completely
    year_match = re.search(r"(20\d{2})", period_name)
    if year_match:
        text = period_name.replace(year_match.group(0), "").strip()
    else:
        text = period_name
    
    # Clean up remaining text
    text = re.sub(r"\s+", " ", text.replace("-", " - ")).strip(" -")
    return text.title()


def calculate_academic_progression_year(all_registrations, current_registration):
    """Calculate the correct academic year (1, 2, 3, 4) based on enrollment timeline."""
    if not all_registrations or not current_registration:
        return 1
    
    # Find the position of current registration in chronological order
    try:
        current_index = all_registrations.index(current_registration)
        
        # Academic year calculation based on enrollment timeline
        # The first two registrations (positions 0, 1) are Year 1
        # The next two registrations (positions 2, 3) are Year 2
        # & so on...
        progression_year = (current_index // 2) + 1
        
        return progression_year
    except ValueError:
        return 1


def calculate_academic_semester(all_registrations, current_registration):
    """Calculate the correct semester (1, 2) based on enrollment timeline position."""
    if not all_registrations or not current_registration:
        return 1
    
    try:
        current_index = all_registrations.index(current_registration)
        
        # Determine semester based on position within the year
        # Even positions (0, 2, 4...) are Semester 1 within that year
        # Odd positions (1, 3, 5...) are Semester 2 within that year
        semester_in_year = (current_index % 2) + 1
        
        return semester_in_year
    except ValueError:
        return 1


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
    """Combine academic year & semester into a university-friendly level label."""

    year_label = format_academic_year_label(academic_year)
    semester_label = format_semester_label(semester)
    return f"{year_label} {semester_label}"


def normalize_gender_key(gender):
    """Normalize free-text gender values into stable dashboard buckets."""

    text = str(gender or "").strip().lower()
    if text == "male":
        return "male"
    if text == "female":
        return "female"
    return "unspecified"


def validate_semester_period_alignment(registration):
    """
    STRICT VALIDATION: Ensure semester aligns with correct period.
    
    Academic Sequence Rules:
    - Semester 1 must align with March-August period
    - Semester 2 must align with August-December period
    - NO cross-mapping allowed between semesters
    """
    if not registration or not registration.period:
        return False, "No registration period data"
    
    semester_num = registration.period.semester
    period_name = registration.period.name.lower()
    
    # Define semester-period mappings based on actual period patterns
    SEMESTER_PERIOD_MAPPINGS = {
        1: ["september", "august"],  # Semester 1: September - December OR August - December
        2: ["march"],  # Semester 2: March - July
    }
    
    # Validate semester exists in mapping
    if semester_num not in SEMESTER_PERIOD_MAPPINGS:
        return False, f"Invalid semester number: {semester_num}"
    
    # Get expected period keywords for this semester
    expected_periods = SEMESTER_PERIOD_MAPPINGS[semester_num]
    
    # Validate period contains expected keywords
    period_valid = any(keyword in period_name for keyword in expected_periods)
    
    if not period_valid:
        return False, f"Semester {semester_num} misaligned with period: {registration.period.name}"
    
    return True, "Valid semester-period alignment"


def validate_semester_chronological_order(registrations):
    """
    STRICT VALIDATION: Ensure semesters follow correct chronological order.
    
    Required Order: Semester 1 (March-August) -> Semester 2 (August-December)
    Most recent should appear on top, but internal ordering must remain logical.
    """
    if not registrations or len(registrations) <= 1:
        return True, "Valid ordering (single or no registration)"
    
    # Sort registrations by academic year & semester
    sorted_registrations = sorted(
        registrations,
        key=lambda reg: (reg.period.academic_year, reg.period.semester)
    )
    
    # Validate semester sequence within each academic year
    for i in range(len(sorted_registrations) - 1):
        current = sorted_registrations[i]
        next_reg = sorted_registrations[i + 1]
        
        # Same academic year: check semester progression
        if current.period.academic_year == next_reg.period.academic_year:
            if current.period.semester >= next_reg.period.semester:
                return False, f"Invalid semester sequence: Semester {current.period.semester} should come before Semester {next_reg.period.semester}"
    
    return True, "Valid chronological ordering"


def get_strict_semester_ordering(registrations):
    """
    STRICT ORDERING: Return registrations in correct chronological order.
    
    Display Rule: Most recent semester appears on top
    Internal Rule: Maintain logical chronological consistency
    """
    if not registrations:
        return []
    
    # First validate all registrations
    for reg in registrations:
        is_valid, message = validate_semester_period_alignment(reg)
        if not is_valid:
            continue  # Skip invalid registrations
    
    # Sort by academic year & semester (chronological order)
    chronological_order = sorted(
        registrations,
        key=lambda reg: (reg.period.academic_year, reg.period.semester)
    )
    
    # Reverse for display (most recent on top)
    display_order = list(reversed(chronological_order))
    
    return display_order


def build_filters(request):
    """Build shared topbar filter metadata from request query parameters."""

    selected_year = request.GET.get("year", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_faculty = request.GET.get("faculty", "").strip()

    periods = list(AcademicPeriod.objects.order_by("name").values("name"))
    years = sorted({extract_period_year(period["name"]) for period in periods if extract_period_year(period["name"])}, reverse=True)
    
    # Filter periods by selected year & create options with display labels
    if selected_year:
        filtered_periods = [period for period in periods if extract_period_year(period["name"]) == selected_year]
        period_options = []
        for period in filtered_periods:
            display_label = format_period_label(period["name"])
            if display_label:
                period_options.append(display_label)
        period_options = sorted(period_options)
    else:
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
    """Build shared sidebar & filter context for dashboard templates."""

    # Get current filter parameters
    filter_params = {}
    for param in ['year', 'period', 'faculty']:
        value = request.GET.get(param, "").strip()
        if value:
            filter_params[param] = value

    items = []
    for item in SIDEBAR_ITEMS:
        # Build URL with filter parameters
        url = reverse(item["url_name"])
        if filter_params:
            query_string = '&'.join([f"{key}={value}" for key, value in filter_params.items()])
            url = f"{url}?{query_string}"
        
        items.append(
            {
                **item,
                "url": url,
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
    """Calculate top-level user & access-control metrics for the system page."""

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
    """Transform managed users into template rows with status & action metadata."""

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
    """Build a reusable registration filter for querysets & annotations."""

    selected_year = request.GET.get("year", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_faculty = request.GET.get("faculty", "").strip()

    filters = Q()
    if selected_year:
        filters &= Q(**{f"{prefix}period__name__icontains": selected_year})
    if selected_period:
        # Find all periods that match the selected display label
        periods = AcademicPeriod.objects.all()
        matching_period_names = []
        for period in periods:
            if format_period_label(period.name) == selected_period:
                matching_period_names.append(period.name)
        
        if matching_period_names:
            period_filter = Q(**{f"{prefix}period__name__in": matching_period_names})
            filters &= period_filter
    if selected_faculty:
        filters &= Q(**{f"{prefix}programme__department__faculty__name": selected_faculty})

    return filters


def get_filtered_registrations(request, include_course_results=True):
    """Return registrations filtered by the active year, period, & faculty."""

    registrations = (
        Registration.objects.select_related(
            "student",
            "programme__department__faculty",
            "period",
        )
        .order_by("student__surname", "student__first_names")
    )
    if include_course_results:
        registrations = registrations.prefetch_related("course_results")

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
    proceed_count = registrations.filter(decision__iexact="PROCEED").count()
    completion_rate = (
        f"{round((proceed_count / total_registered) * 100)}%"
        if total_registered
        else "0%"
    )
    avg_mark = filtered_results.aggregate(value=Avg("mark"))["value"]
    
    # Calculate first year retention using the new dynamic method
    from .overview.services import _calculate_first_year_retention
    first_year_retention = _calculate_first_year_retention(registrations)
    
    # Handle special cases for retention display
    if first_year_retention == "No data available":
        retention_display = "No data available"
    elif first_year_retention == "0%":
        retention_display = "Retention cannot be calculated for selected filters"
    else:
        retention_display = first_year_retention
    
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
        "first_year_retention": retention_display,
        "at_risk": at_risk_count,
    }

def build_programme_rows(programmes):
    """Delegate programme row shaping to the feature package for compatibility."""

    from .programmes.services import build_programme_rows as feature_build_programme_rows

    return feature_build_programme_rows(programmes)


def get_programme_summary_values(request, search_query=""):
    """Delegate programme summary metrics to the feature package for compatibility."""

    from .programmes.services import get_programme_summary_values as feature_get_programme_summary_values

    return feature_get_programme_summary_values(request, search_query)


def normalize_decision_label(decision):
    """Normalize a registration decision value for consistent user-facing display."""

    text = str(decision or "").strip()
    normalized = text.title() if text else "Not Recorded"
    return normalized.replace(" And ", " & ")


def build_initials(name):
    """Build a compact avatar label from a student's full name."""

    parts = [part for part in re.split(r"\s+", str(name or "").strip()) if part]
    if not parts:
        return "NA"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def assess_student_risk(registrations):
    """Delegate risk scoring to the feature package for compatibility."""

    from .risk.services import assess_student_risk as feature_assess_student_risk

    return feature_assess_student_risk(registrations)


def build_student_risk_profiles(request, search_query=""):
    """Delegate student risk profiling to the feature package for compatibility."""

    from .risk.services import build_student_risk_profiles as feature_build_student_risk_profiles

    return feature_build_student_risk_profiles(request, search_query)


def format_risk_monitor_drivers(risk_driver_text):
    """Delegate risk table driver cleanup to the feature package for compatibility."""

    from .risk.services import format_risk_monitor_drivers as feature_format_risk_monitor_drivers

    return feature_format_risk_monitor_drivers(risk_driver_text)


def format_insight_flagged_meta(risk_driver_text, academic_level):
    """Delegate insight-card risk meta formatting to the feature package for compatibility."""

    from .risk.services import format_insight_flagged_meta as feature_format_insight_flagged_meta

    return feature_format_insight_flagged_meta(risk_driver_text, academic_level)


def build_risk_rows(request, search_query=""):
    """Delegate risk register row building to the feature package for compatibility."""

    from .risk.services import build_risk_rows as feature_build_risk_rows

    return feature_build_risk_rows(request, search_query)


def get_risk_summary_values(request, search_query=""):
    """Delegate risk summary metrics to the feature package for compatibility."""

    from .risk.services import get_risk_summary_values as feature_get_risk_summary_values

    return feature_get_risk_summary_values(request, search_query)


def build_insight_scope_pills(request):
    """Build small scope badges that summarize the active insights filter context."""

    from .insights.services import build_insight_scope_pills as feature_build_insight_scope_pills

    return feature_build_insight_scope_pills(request)


def build_insights_dashboard_data(request):
    """Assemble the live operational signals & recommendation content for Insights."""

    from .insights.services import build_insights_dashboard_data as feature_build_insights_dashboard_data

    return feature_build_insights_dashboard_data(request)


@login_required_except_domains()
def dashboard_home(request):
    """Delegate home-page rendering to the overview feature package."""

    from .overview.views import dashboard_home as feature_dashboard_home

    return feature_dashboard_home(request)


def build_student_directory_search_q(search_query):
    """Build the reusable search filter for the students directory."""

    if not search_query:
        return Q()

    return (
        Q(student__first_names__icontains=search_query)
        | Q(student__surname__icontains=search_query)
        | Q(student__registration_number__icontains=search_query)
        | Q(programme__name__icontains=search_query)
        | Q(programme__department__name__icontains=search_query)
    )


@login_required_except_domains()
def student_list(request):
    """Render the paginated student directory with shared dashboard filters."""

    search_query = request.GET.get("q", "").strip()
    filtered_registrations = get_filtered_registrations(request, include_course_results=False)
    registrations = filtered_registrations.filter(build_student_directory_search_q(search_query))

    latest_registration = registrations.filter(student_id=OuterRef("pk")).order_by("-period__external_id", "-id")
    average_mark = (
        CourseResult.objects.filter(
            build_registration_filter_q(request, prefix="registration__"),
            registration__student_id=OuterRef("pk"),
        )
        .exclude(mark__isnull=True)
        .values("registration__student_id")
        .annotate(value=Avg("mark"))
        .values("value")[:1]
    )
    matching_student_ids = registrations.order_by().values("student_id").distinct()

    sort_key = request.GET.get("sort", "name")
    sort_direction = request.GET.get("direction", "asc")
    if sort_direction not in ("asc", "desc"):
        sort_direction = "asc"

    sort_column_map = {
        "name": ["surname", "first_names", "registration_number"],
        "department": ["latest_department", "surname", "first_names"],
        "programme": ["latest_programme", "surname", "first_names"],
        "average_mark": ["scoped_average_mark", "surname", "first_names"],
        "decision": ["latest_decision", "surname", "first_names"],
        "gender": ["gender", "surname", "first_names"],
    }
    if sort_key not in sort_column_map:
        sort_key = "name"
    sort_fields = sort_column_map[sort_key]
    order_prefix = "-" if sort_direction == "desc" else ""
    ordered_fields = [f"{order_prefix}{field}" for field in sort_fields]

    students_queryset = (
        Student.objects.filter(pk__in=Subquery(matching_student_ids))
        .annotate(
            latest_department=Subquery(
                latest_registration.values("programme__department__name")[:1],
                output_field=CharField(),
            ),
            latest_programme=Subquery(
                latest_registration.values("programme__name")[:1],
                output_field=CharField(),
            ),
            latest_decision=Subquery(
                latest_registration.values("decision")[:1],
                output_field=CharField(),
            ),
            scoped_average_mark=Subquery(
                average_mark,
                output_field=FloatField(),
            ),
        )
        .order_by(*ordered_fields)
    )

    paginator = Paginator(students_queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_window_start = max(page_obj.number - 2, 1)
    page_window_end = min(page_obj.number + 2, paginator.num_pages)
    student_rows = [
        {
            "name": student.full_name,
            "department": student.latest_department or "",
            "programme": (student.latest_programme or "").replace("Bsc", "BSc").replace("Bcom", "BCom"),
            "average_mark": round(student.scoped_average_mark or 0),
            "decision": str(student.latest_decision or "").title().replace(" And ", " & "),
            "gender": student.gender.title(),
            "detail_slug": student.registration_number.lower(),
        }
        for student in page_obj.object_list
    ]

    context = build_layout_context(request, "students")
    context.update(
        {
            "page_title": "Students Dashboard",
            "students": student_rows,
            "page_obj": page_obj,
            "page_numbers": range(page_window_start, page_window_end + 1),
            "search_query": search_query,
            "sort_key": sort_key,
            "sort_direction": sort_direction,
            "total_students": paginator.count,
        }
    )
    return render(request, "dashboard/students.html", context)


@login_required_except_domains()
def student_detail(request, slug):
    """Render a student profile with term tabs & course results with advanced filter synchronization."""

    student_record = get_object_or_404(
        Student.objects.prefetch_related(
            "registrations__course_results__course",
            "registrations__programme__department",
            "registrations__period",
        ),
        registration_number__iexact=slug,
    )
    
    # Get filter parameters
    selected_year = request.GET.get("year", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_faculty = request.GET.get("faculty", "").strip()
    selected_term_id = request.GET.get("term", "").strip()
    
    # Get all registrations for the student
    all_registrations = list(
        student_record.registrations.select_related(
            "programme__department__faculty", 
            "period"
        ).order_by("period__academic_year", "period__semester")
    )
    
    # Filter registrations based on actual enrollment record validation
    filtered_registrations = []
    for registration in all_registrations:
        # Calculate progression year based on actual enrollment timeline
        progression_year = calculate_academic_progression_year(all_registrations, registration)
        calculated_semester = calculate_academic_semester(all_registrations, registration)
        semester_label = format_semester_label(calculated_semester)
        faculty_name = registration.programme.department.faculty.name
        
        # Check Year filter against actual enrollment
        year_match = True
        if selected_year and selected_year != "All":
            # Extract calendar year from selected year (e.g., "2025" from "Year 2025")
            calendar_year = selected_year.replace("Year ", "").strip() if selected_year.startswith("Year ") else selected_year
            registration_year = str(registration.period.external_id)[:4] if registration.period.external_id else str(registration.period.academic_year)
            
            if registration_year != calendar_year:
                year_match = False
        
        # Check Period filter against actual enrollment
        period_match = True
        if selected_period and selected_period != "All":
            # Check if this registration's period name matches the selected period
            registration_period_label = format_period_label(registration.period.name)
            if registration_period_label.lower() != selected_period.lower():
                period_match = False
        
        # Check Faculty filter against actual enrollment
        faculty_match = True
        if selected_faculty and selected_faculty != "All":
            if faculty_name != selected_faculty:
                faculty_match = False
        
        # Only include registration if ALL filters match actual enrollment
        if year_match and period_match and faculty_match:
            filtered_registrations.append(registration)
    
    # If no registrations match the filters, show empty state for content but still show tabs
    show_empty_content = not filtered_registrations and (selected_year or selected_period or (selected_faculty and selected_faculty != "All"))
    
    # Create specific empty state message based on which filters are active
    empty_state_message = ""
    if show_empty_content:
        if selected_faculty and selected_faculty != "All":
            if selected_year and selected_year != "All":
                empty_state_message = f"Student not found in {selected_faculty} for {selected_year}. Try adjusting your filters."
            elif selected_period and selected_period != "All":
                empty_state_message = f"Student not found in {selected_faculty} for {selected_period}. Try adjusting your filters."
            else:
                empty_state_message = f"Student not found in {selected_faculty}. Try selecting a different faculty."
        elif selected_year and selected_year != "All":
            if selected_period and selected_period != "All":
                empty_state_message = f"Student not found for {selected_year} {selected_period}. Try adjusting your filters."
            else:
                empty_state_message = f"Student not found for {selected_year}. Try selecting a different year."
        elif selected_period and selected_period != "All":
            empty_state_message = f"Student not found for {selected_period}. Try selecting a different period."
        else:
            empty_state_message = "No records found for the selected filters. Try adjusting your filters."
            
    # Determine selected registration based on filters and tab selection
    latest_registration = all_registrations[-1] if all_registrations else None
    selected_registration = latest_registration
    
    if selected_term_id:
        try:
            # Find the selected registration in all registrations
            selected_registration = next(
                registration for registration in all_registrations 
                if registration.id == int(selected_term_id)
            )
        except (StopIteration, ValueError):
            # If selected term not found, use latest registration
            selected_registration = latest_registration
    elif filtered_registrations:
        # If no specific term selected but we have filtered results, use the most recent filtered one
        selected_registration = filtered_registrations[-1] if filtered_registrations else latest_registration
    elif selected_year or selected_period or (selected_faculty and selected_faculty != "All"):
        # If filters are active but no matching registrations, use latest
        selected_registration = latest_registration
    
    # Calculate cumulative grade based on progressive logic with enrollment validation
    cumulative_registrations = []
    
    # Use progressive logic when a specific registration/tab is selected and matches filters
    if selected_registration and selected_registration in filtered_registrations:
        # Selected registration is valid - use progressive cumulative logic
        for registration in all_registrations:
            # Check if this registration should be included in cumulative calculation
            include_in_cumulative = True
            
            # For cumulative calculation, include all previous periods up to selected registration
            # based on actual enrollment timeline
            
            # Apply Faculty filter to cumulative calculation
            if selected_faculty and selected_faculty != "All":
                if registration.programme.department.faculty.name != selected_faculty:
                    include_in_cumulative = False
            
            # Include if it's before or equal to selected registration (progressive accumulation)
            if include_in_cumulative:
                # Check if this registration comes before or at the same time as selected_registration
                if (registration.period.academic_year < selected_registration.period.academic_year or
                    (registration.period.academic_year == selected_registration.period.academic_year and
                     registration.period.semester <= selected_registration.period.semester)):
                    cumulative_registrations.append(registration)
    elif filtered_registrations:
        # Use filtered registrations for cumulative calculation
        cumulative_registrations = filtered_registrations
    else:
        # No valid selection - include all registrations
        cumulative_registrations = all_registrations
    
    # Get all course results for cumulative calculation
    all_cumulative_results = []
    for registration in cumulative_registrations:
        all_cumulative_results.extend(registration.course_results.all())
    
    # Apply faculty filter to cumulative results
    if selected_faculty and selected_faculty != "All":
        cumulative_results = [
            result for result in all_cumulative_results
            if result.registration.programme.department.faculty.name == selected_faculty
        ]
    else:
        cumulative_results = all_cumulative_results
    
    # Calculate weighted cumulative grade
    if cumulative_results:
        total_weighted_marks = 0
        total_weights = 0
        course_count = 0
        
        for result in cumulative_results:
            mark = result.mark or 0
            # Use course credits as weight, default to 1 if not available
            weight = getattr(result.course, 'credits', 1) if hasattr(result.course, 'credits') else 1
            total_weighted_marks += mark * weight
            total_weights += weight
            course_count += 1
        
        if total_weights > 0:
            weighted_average = total_weighted_marks / total_weights
            # Round to nearest whole number
            average_mark = round(weighted_average)
        else:
            average_mark = 0
    else:
        average_mark = 0
    
    # Get results - STRICT filter-driven data rendering
    results = []
    display_empty_message = False
    
    # Validate that selected filters correspond to student's actual academic progression
    if selected_registration:
        # Check if selected registration is part of student's valid academic progression
        student_academic_years = set()
        for registration in all_registrations:
            progression_year = calculate_academic_progression_year(all_registrations, registration)
            student_academic_years.add(progression_year)
        
        selected_academic_year = calculate_academic_progression_year(all_registrations, selected_registration)
        
        # Validate academic progression access
        if selected_academic_year not in student_academic_years:
            # Student is trying to access non-existent academic year
            display_empty_message = True
            empty_state_message = f"No courses found — student not yet in Year {selected_academic_year}."
        else:
            # TEMP: Disable validation for debugging
            # is_semester_valid, semester_message = validate_semester_period_alignment(selected_registration)
            # 
            # if not is_semester_valid:
            #     # Critical data integrity violation - semester misaligned with period
            #     display_empty_message = True
            #     empty_state_message = "No courses found for this semester due to mismatched academic data."
            #     print(f"CRITICAL ERROR: {semester_message} - Registration ID: {selected_registration.id}")
            # else:
                # Valid semester-period alignment - get results with strict filter application
                registration_results = selected_registration.course_results.all()
                
                # Apply faculty filter (if not "All")
                if selected_faculty and selected_faculty != "All":
                    if selected_registration.programme.department.faculty.name == selected_faculty:
                        results = [
                            {
                                "code": result.course.code,
                                "course": result.course.name,
                                "period": selected_registration.period.external_id,
                                "mark": round(result.mark or 0),
                            }
                            for result in registration_results
                        ]
                    else:
                        # Faculty filter doesn't match - no results
                        display_empty_message = True
                        empty_state_message = f"No courses found for the selected filters."
                else:
                    # No faculty filter or "All" selected - show all results
                    results = [
                        {
                            "code": result.course.code,
                            "course": result.course.name,
                            "period": selected_registration.period.external_id,
                            "mark": round(result.mark or 0),
                        }
                        for result in registration_results
                    ]
    
    elif filtered_registrations:
        # Filter-based rendering with strict validation
        for registration in filtered_registrations:
            # Validate semester-period alignment for each registration
            is_semester_valid, semester_message = validate_semester_period_alignment(registration)
            
            if not is_semester_valid:
                # Skip registrations with invalid semester-period alignment
                continue
            
            registration_results = registration.course_results.all()
            
            # Apply faculty filter
            if selected_faculty and selected_faculty != "All":
                if registration.programme.department.faculty.name == selected_faculty:
                    results.extend([
                        {
                            "code": result.course.code,
                            "course": result.course.name,
                            "period": registration.period.external_id,
                            "mark": round(result.mark or 0),
                        }
                        for result in registration_results
                    ])
                else:
                    # Faculty filter doesn't match - skip this registration
                    continue
            else:
                # No faculty filter or "All" selected
                results.extend([
                    {
                        "code": result.course.code,
                        "course": result.course.name,
                        "period": registration.period.external_id,
                        "mark": round(result.mark or 0),
                    }
                    for result in registration_results
                ])
        
        # Check if any results were found after filtering
        if not results:
            display_empty_message = True
            empty_state_message = "No courses found for the selected filters."
    
    else:
        # No specific registration or filters - default to most recent
        if all_registrations:
            most_recent_registration = all_registrations[-1]  # Last registration (most recent)
            registration_results = most_recent_registration.course_results.all()
            
            # Apply faculty filter
            if selected_faculty and selected_faculty != "All":
                if most_recent_registration.programme.department.faculty.name == selected_faculty:
                    results = [
                        {
                            "code": result.course.code,
                            "course": result.course.name,
                            "period": most_recent_registration.period.external_id,
                            "mark": round(result.mark or 0),
                        }
                        for result in registration_results
                    ]
                else:
                    display_empty_message = True
                    empty_state_message = "No courses found for the selected filters."
            else:
                results = [
                    {
                        "code": result.course.code,
                        "course": result.course.name,
                        "period": most_recent_registration.period.external_id,
                        "mark": round(result.mark or 0),
                    }
                    for result in registration_results
                ]
        else:
            # No registrations at all
            display_empty_message = True
            empty_state_message = "No courses found for this student."
    
    # Build year-based dropdown tabs with STRICT semester ordering
    year_dropdown_tabs = []
    # TEMP: Disable strict validation for debugging
    validated_registrations = all_registrations  # TEMP: Use all registrations
    
    # TEMP: Skip chronological validation for debugging
    # is_order_valid, order_message = validate_semester_chronological_order(validated_registrations)
    # if not is_order_valid:
    #     pass
    
    # Group validated registrations by academic progression year
    year_groups = {}
    for registration in validated_registrations:
        progression_year = calculate_academic_progression_year(validated_registrations, registration)
        if progression_year not in year_groups:
            year_groups[progression_year] = []
        year_groups[progression_year].append(registration)
    
    # Create dropdown tabs for each year (most recent first)
    for year in sorted(year_groups.keys(), reverse=True):
        registrations = year_groups[year]
        year_label = f"Year {year}"
        
        # Check if this year has an active semester selected
        active_semester = None
        for registration in registrations:
            if selected_registration and registration.id == selected_registration.id:
                active_semester = registration
                break
        
        # Update year_label to show year and semester only
        if active_semester:
            calculated_semester = calculate_academic_semester(validated_registrations, active_semester)
            semester_label = format_semester_label(calculated_semester)
            year_label = f"Year {year} {semester_label}"
        
        # Create semester options for this year
        semester_options = []
        is_year_active = False
        
        for registration in registrations:
            # TEMP: Disable strict semester validation for debugging
            # is_semester_valid, semester_message = validate_semester_period_alignment(registration)
            # 
            # if not is_semester_valid:
            #     # Skip invalid semester options
            #     print(f"WARNING: Skipping invalid semester option - {semester_message} - Registration ID: {registration.id}")
            #     continue
            is_semester_valid = True  # TEMP: Always valid for debugging
            
            calculated_semester = calculate_academic_semester(validated_registrations, registration)
            semester_label = format_semester_label(calculated_semester)
            period_label = format_period_label(registration.period.name)
            
            # Determine if this semester should be active
            is_semester_active = False
            if selected_registration and registration.id == selected_registration.id:
                is_semester_active = True
                is_year_active = True
            elif not selected_registration:
                # When no specific tab selected, highlight based on filter context
                year_match = True
                period_match = True
                faculty_match = True
                
                # Check Year filter
                if selected_year and selected_year != "All":
                    calendar_year = selected_year.replace("Year ", "").strip() if selected_year.startswith("Year ") else selected_year
                    registration_year = str(registration.period.external_id)[:4] if registration.period.external_id else str(registration.period.academic_year)
                    if registration_year != calendar_year:
                        year_match = False
                
                # Check Period filter
                if selected_period and selected_period != "All":
                    registration_period_label = format_period_label(registration.period.name)
                    if registration_period_label.lower() != selected_period.lower():
                        period_match = False
                
                # Check Faculty filter - use filter context for highlighting
                if selected_faculty and selected_faculty != "All":
                    faculty_match = True  # Always match for highlighting purposes
                else:
                    faculty_match = True
                
                # Highlight if matches all filters or no filters active
                if year_match and period_match and faculty_match:
                    is_semester_active = True
                    is_year_active = True
                elif not (selected_year or selected_period or (selected_faculty and selected_faculty != "All")):
                    # If no filters, highlight most recent semester
                    if year == sorted(year_groups.keys(), reverse=True)[0] and registration == registrations[-1]:
                        is_semester_active = True
                        is_year_active = True
            
            semester_options.append({
                "id": registration.id,
                "label": semester_label,
                "period_name": period_label,
                "is_active": is_semester_active,
                "registration": registration
            })
        
        # Sort semester options with most recent first (semester 2 before semester 1)
        semester_options.sort(key=lambda x: calculate_academic_semester(validated_registrations, x["registration"]), reverse=True)
        
        year_dropdown_tabs.append({
            "year": year,
            "year_label": year_label,
            "is_active": is_year_active,
            "semester_selected": bool(active_semester),
            "semesters": semester_options
        })
        
            
    # For backward compatibility, create flat term_tabs from dropdown tabs (for existing template logic)
    term_tabs = []
    for year_tab in year_dropdown_tabs:
        for semester in year_tab["semesters"]:
            # Use clean year label without semester for term_tabs
            clean_year_label = f"Year {year_tab['year']}"
            term_tabs.append({
                "id": semester["id"],
                "label": f"{clean_year_label} {semester['label']}",
                "period_name": semester["period_name"],
                "is_active": semester["is_active"],
            })
    
    
    student = {
        "name": student_record.full_name,
        "student_number": student_record.registration_number,
        "programme": selected_registration.programme.normalized_name if selected_registration else "",
        "academic_level": (
            f"Year {calculate_academic_progression_year(all_registrations, selected_registration)} Semester {calculate_academic_semester(all_registrations, selected_registration)}"
            if selected_registration
            else ""
        ),
        "term_name": selected_registration.period.name.title() if selected_registration else "",
        "decision": selected_registration.decision.title().replace(" And ", " & ") if selected_registration else "",
        "gender": student_record.gender.title(),
        "age": "",
        "place_of_birth": student_record.place_of_birth,
        "cumulative_grade": round(average_mark, 1),
        "term_tabs": term_tabs,
        "year_dropdown_tabs": year_dropdown_tabs,
        "results": results,
        "show_empty_content": display_empty_message,
        "no_data_message": empty_state_message,
        "selected_filters": {
            "year": selected_year,
            "period": selected_period, 
            "faculty": selected_faculty,
        }
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
def insights_view(request):
    """Render the institutional insights board with live flagged-student signals."""

    from .insights.views import insights_view as feature_insights_view

    return feature_insights_view(request)


@login_required_except_domains()
def programme_view(request):
    """Delegate the programmes page to the feature package for compatibility."""

    from .programmes.views import programme_view as feature_programme_view

    return feature_programme_view(request)


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
    managed_users = user_model.objects.select_related("user_type").order_by("email")
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
    """Delegate home metric hydration to the overview feature package."""

    from .overview.views import dashboard_home_metrics as feature_dashboard_home_metrics

    return feature_dashboard_home_metrics(request)


@ajax_login_required
@require_GET
def programme_metrics(request):
    """Delegate programme metrics JSON to the feature package for compatibility."""

    from .programmes.views import programme_metrics as feature_programme_metrics

    return feature_programme_metrics(request)



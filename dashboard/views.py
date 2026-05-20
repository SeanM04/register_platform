import re
from urllib.parse import urlencode

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
from django.conf import settings as django_settings
from services.chatbot_service import get_chatbot_provider_status
from .models import AcademicPeriod, AuditLog, CourseResult, Faculty, PlatformSetting, Programme, Registration, Student
from .student_history import (
    build_student_timeline,
    build_transcript_summary,
    calculate_cumulative_average,
    extract_registration_year_semester,
    format_academic_level_label as format_programme_level_label,
    format_semester_label as format_programme_semester_label,
    format_year_label as format_programme_year_label,
)

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
    {"key": "reports", "label": "Reports", "url_name": "dashboard:reports", "requires_admin": True},
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
CHATBOT_SUGGESTIONS = {
    "dashboard": [
        "Summarize the current dashboard scope.",
        "Which faculty looks most pressured right now?",
        "What is the current pass rate in this scope?",
    ],
    "students": [
        "Summarize the student record I am viewing.",
        "Explain the current period and decision.",
        "What should I pay attention to in this record?",
    ],
    "programmes": [
        "Which programme is strongest in this scope?",
        "Compare the top visible programmes.",
        "What does the programme chart mean?",
    ],
    "demographics": [
        "Summarize the demographic picture in this scope.",
        "Which demographic pattern stands out most?",
        "What does the origin map tell us?",
    ],
    "academic-levels": [
        "Which academic level is under the most pressure?",
        "Summarize academic performance by level.",
        "What does this level distribution mean?",
    ],
    "completion": [
        "Explain the completion rules.",
        "What causes zero completion?",
        "Summarize the current completion scope.",
    ],
    "graduation": [
        "Explain the graduation rules.",
        "What does on-time graduation mean?",
        "Summarize the current graduation scope.",
    ],
    "risk": [
        "How should I read the risk bands?",
        "What is the main driver of risk here?",
        "Summarize the current watchlist.",
    ],
    "insights": [
        "Summarize the current insights page.",
        "What action should the institution take next?",
        "Which trigger is driving the watchlist?",
    ],
    "system-management": [
        "Explain what this admin page is for.",
        "How do platform roles work here?",
        "What should administrators review first?",
    ],
}


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
    """Return the registration's official programme year from the stored period."""
    if not current_registration:
        return 1
    year, _ = extract_registration_year_semester(current_registration)
    return year


def calculate_academic_semester(all_registrations, current_registration):
    """Return the registration's official semester from the stored period."""
    if not current_registration:
        return 1
    _, semester = extract_registration_year_semester(current_registration)
    return semester


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

    return format_programme_level_label(academic_year, semester)


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
    chatbot_status = get_chatbot_provider_status()
    context.update({
        "sidebar_items": items,
        "chatbot_bootstrap": {
            "enabled": chatbot_status["enabled"],
            "ai_available": chatbot_status["ai_available"],
            "provider": chatbot_status["provider"],
            "endpoint": reverse("chatbot:message"),
            "stream_endpoint": reverse("chatbot:stream"),
            "page_key": active_key,
            "page_label": next((item["label"] for item in SIDEBAR_ITEMS if item["key"] == active_key), "Workspace"),
            "suggestions": CHATBOT_SUGGESTIONS.get(active_key, CHATBOT_SUGGESTIONS["dashboard"]),
        },
    })
    return context


def _registration_calendar_year(registration):
    """Return the topbar year value for a registration's real academic period."""

    period = registration.period
    period_year = extract_period_year(period.name)
    if period_year:
        return period_year

    external_id = str(period.external_id or "").strip()
    if len(external_id) >= 4:
        return external_id[:4]

    return str(period.academic_year or "").strip()


def _registration_period_label(registration):
    """Return the topbar period value for a registration."""

    return format_period_label(registration.period.name)


def _registration_has_course_results(registration):
    """Return whether a registration can render rows in the student results table."""

    return bool(registration.course_results.all())


def _registration_progression_year_label(registrations, registration):
    """Return the student-facing academic progression year label for a registration."""

    return format_programme_year_label(calculate_academic_progression_year(registrations, registration))


def _ordered_unique(values):
    """Return stable unique values while preserving display order."""

    seen = set()
    unique_values = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _student_list_back_url(request):
    """Return the original students-list URL for Back navigation when available."""

    return_to = request.GET.get("return_to", "").strip()
    if return_to:
        return return_to

    allowed_keys = ("page", "q", "year", "period", "faculty", "sort", "direction")
    params = []
    for key in allowed_keys:
        value = request.GET.get(key, "").strip()
        if value:
            params.append((key, value))

    base_url = reverse("dashboard:students")
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"


def _build_student_detail_filter_context(registrations, requested_year, requested_period, requested_faculty):
    """Build topbar filters constrained to the selected student's own records."""

    if not registrations:
        return {
            "selected_year": "",
            "selected_period": "",
            "selected_faculty": "",
            "filters": [
                {"label": "Year", "name": "year", "selected": "", "options": [], "all_label": None, "disabled": True},
                {"label": "Period", "name": "period", "selected": "", "options": [], "all_label": None, "disabled": True},
                {"label": "Faculty", "name": "faculty", "selected": "", "options": [], "all_label": None, "disabled": True},
            ],
        }

    latest_registration = registrations[-1]
    faculty_options = sorted(
        {
            registration.programme.department.faculty.name
            for registration in registrations
            if registration.programme and registration.programme.department and registration.programme.department.faculty
        }
    )
    latest_faculty = latest_registration.programme.department.faculty.name
    selected_faculty = requested_faculty if requested_faculty in faculty_options else latest_faculty

    faculty_registrations = [
        registration
        for registration in registrations
        if registration.programme.department.faculty.name == selected_faculty
    ] or registrations

    year_options = _ordered_unique(
        _registration_progression_year_label(registrations, registration)
        for registration in reversed(faculty_registrations)
    )
    latest_year = _registration_progression_year_label(registrations, faculty_registrations[-1])
    selected_year = requested_year if requested_year in year_options else ""
    if not selected_year and requested_year:
        matching_calendar_registrations = [
            registration
            for registration in faculty_registrations
            if _registration_calendar_year(registration) == requested_year
            and (not requested_period or _registration_period_label(registration).lower() == requested_period.lower())
        ] or [
            registration
            for registration in faculty_registrations
            if _registration_calendar_year(registration) == requested_year
        ]
        if matching_calendar_registrations:
            selected_year = _registration_progression_year_label(registrations, matching_calendar_registrations[-1])
    selected_year = selected_year or latest_year

    year_registrations = [
        registration
        for registration in faculty_registrations
        if _registration_progression_year_label(registrations, registration) == selected_year
    ] or faculty_registrations

    period_options = _ordered_unique(
        _registration_period_label(registration)
        for registration in year_registrations
    )
    latest_period = _registration_period_label(year_registrations[-1])
    selected_period = requested_period if requested_period in period_options else latest_period

    return {
        "selected_year": selected_year,
        "selected_period": selected_period,
        "selected_faculty": selected_faculty,
        "filters": [
            {
                "label": "Year",
                "name": "year",
                "selected": selected_year,
                "options": year_options,
                "all_label": None,
                "disabled": len(year_options) <= 1,
            },
            {
                "label": "Period",
                "name": "period",
                "selected": selected_period,
                "options": period_options,
                "all_label": None,
                "disabled": len(period_options) <= 1,
            },
            {
                "label": "Faculty",
                "name": "faculty",
                "selected": selected_faculty,
                "options": faculty_options,
                "all_label": None,
                "disabled": len(faculty_options) <= 1,
            },
        ],
    }


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
            "age": student.current_age,
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
    return_to = request.GET.get("return_to", "").strip()
    back_to_students_url = _student_list_back_url(request)
    
    # Get all registrations for the student
    all_registrations = list(
        student_record.registrations.select_related(
            "programme__department__faculty", 
            "period"
        ).order_by("period__external_id", "id")
    )
    faculty_options = sorted(
        {
            registration.programme.department.faculty.name
            for registration in all_registrations
            if registration.programme and registration.programme.department and registration.programme.department.faculty
        }
    )
    latest_registration = all_registrations[-1] if all_registrations else None
    default_faculty = latest_registration.programme.department.faculty.name if latest_registration else ""
    selected_faculty = selected_faculty if selected_faculty in faculty_options else default_faculty

    faculty_registrations = [
        registration
        for registration in all_registrations
        if not selected_faculty or registration.programme.department.faculty.name == selected_faculty
    ] or all_registrations

    timeline = build_student_timeline(faculty_registrations)
    groups = timeline["groups"]
    groups_by_key = timeline["groups_by_key"]

    year_options = [format_programme_year_label(group["year"]) for group in sorted(groups, key=lambda item: item["year"], reverse=True)]
    year_options = _ordered_unique(year_options)
    selected_year = selected_year if selected_year in year_options else (year_options[0] if year_options else "")

    year_groups = [group for group in groups if group["year_label"] == selected_year] or groups
    period_options = _ordered_unique(
        format_period_label(group["latest_registration"].period.name)
        for group in sorted(year_groups, key=lambda item: item["semester"], reverse=True)
    )
    selected_period = selected_period if selected_period in period_options else (period_options[0] if period_options else "")

    visible_groups = [
        group
        for group in groups
        if (not selected_year or group["year_label"] == selected_year)
        and (
            not selected_period
            or format_period_label(group["latest_registration"].period.name) == selected_period
        )
    ]
    show_empty_content = not visible_groups and bool(selected_year or selected_period or selected_faculty)
    empty_state_message = "No courses found for the selected filters." if show_empty_content else ""

    selected_group = None
    if selected_term_id:
        selected_group = groups_by_key.get(selected_term_id)
    if not selected_group or selected_group not in visible_groups:
        selected_group = visible_groups[-1] if visible_groups else (groups[-1] if groups else None)

    selected_group_key = selected_group["key"] if selected_group else None
    selected_registration = selected_group["latest_registration"] if selected_group else latest_registration
    average_mark = calculate_cumulative_average(groups, selected_group_key)

    results = []
    result_sections = []
    show_result_sections = False
    if selected_group:
        registrations_in_display_order = sorted(
            selected_group["registrations"],
            key=lambda registration: (
                getattr(getattr(registration, "period", None), "external_id", 0) or 0,
                registration.id or 0,
            ),
            reverse=True,
        )
        rows_by_registration_id = {}
        for row in selected_group["results"]:
            registration_id = getattr(row["registration"], "id", None)
            rows_by_registration_id.setdefault(registration_id, []).append(
                {
                    "code": row["course_code"],
                    "course": row["course_display_name"],
                    "period": row["period_name"],
                    "mark": row["mark_value"] if row["mark_value"] is not None else "--",
                    "status": row["status_label"],
                    "attempt_tags": row["attempt_tags"],
                    "is_repeat_attempt": row["is_repeat_attempt"],
                    "is_carried_attempt": row["is_carried_attempt"],
                    "is_failing": row["is_failing"],
                    "is_awaiting": row["mark_value"] is None,
                }
            )

        for registration in registrations_in_display_order:
            registration_rows = rows_by_registration_id.get(registration.id, [])
            if not registration_rows:
                continue
            result_sections.append(
                {
                    "period_name": str(getattr(getattr(registration, "period", None), "name", "") or "").strip(),
                    "results": registration_rows,
                }
            )
            results.extend(registration_rows)

        show_result_sections = len(result_sections) > 1 and any(
            row["is_repeat_attempt"] or row["is_carried_attempt"]
            for row in results
        )

    year_dropdown_tabs = []
    years_present = sorted({group["year"] for group in groups}, reverse=True)
    for year in years_present:
        groups_in_year = sorted(
            [group for group in groups if group["year"] == year],
            key=lambda item: item["semester"],
            reverse=True,
        )
        semester_options = []
        for group in groups_in_year:
            semester_query = urlencode(
                {
                    "term": group["key"],
                    "year": group["year_label"],
                    "period": format_period_label(group["latest_registration"].period.name),
                    "faculty": selected_faculty,
                    "return_to": return_to,
                }
            )
            semester_options.append(
                {
                    "id": group["key"],
                    "label": group["semester_label"],
                    "selected_label": f"{group['year_label']} {group['semester_label']}",
                    "period_name": group["period_display"],
                    "is_active": selected_group_key == group["key"],
                    "url_query": semester_query,
                }
            )

        active_semester = next(
            (option for option in semester_options if option["is_active"]),
            None,
        )

        year_dropdown_tabs.append(
            {
                "year": year,
                "year_label": format_programme_year_label(year),
                "display_label": active_semester["selected_label"] if active_semester else format_programme_year_label(year),
                "is_active": any(option["is_active"] for option in semester_options),
                "semester_selected": any(option["is_active"] for option in semester_options),
                "semesters": semester_options,
            }
        )

    term_tabs = [
        {
            "id": semester["id"],
            "label": f"{year_tab['year_label']} {semester['label']}",
            "period_name": semester["period_name"],
            "is_active": semester["is_active"],
        }
        for year_tab in year_dropdown_tabs
        for semester in year_tab["semesters"]
    ]

    student_filter_context = {
        "selected_year": selected_year,
        "selected_period": selected_period,
        "selected_faculty": selected_faculty,
        "filters": [
            {
                "label": "Year",
                "name": "year",
                "selected": selected_year,
                "options": year_options,
                "all_label": None,
                "disabled": len(year_options) <= 1,
            },
            {
                "label": "Period",
                "name": "period",
                "selected": selected_period,
                "options": period_options,
                "all_label": None,
                "disabled": len(period_options) <= 1,
            },
            {
                "label": "Faculty",
                "name": "faculty",
                "selected": selected_faculty,
                "options": faculty_options,
                "all_label": None,
                "disabled": len(faculty_options) <= 1,
            },
        ],
    }

    student = {
        "name": student_record.full_name,
        "student_number": student_record.registration_number,
        "programme": selected_registration.programme.normalized_name if selected_registration else "",
        "academic_level": selected_group["academic_level_label"] if selected_group else "",
        "term_name": (
            str(getattr(getattr(selected_registration, "period", None), "name", "") or "").strip()
            if selected_registration else ""
        ),
        "decision": selected_registration.decision.title().replace(" And ", " & ") if selected_registration and selected_registration.decision else "",
        "gender": student_record.gender.title(),
        "age": student_record.current_age if student_record.current_age is not None else None,
        "age_with_details": student_record.age_with_details,
        "age_category": student_record.age_category,
        "date_of_birth": student_record.date_of_birth.strftime('%B %d, %Y') if student_record.date_of_birth else None,
        "place_of_birth": student_record.place_of_birth,
        "cumulative_grade": round(average_mark),
        "term_tabs": term_tabs,
        "year_dropdown_tabs": year_dropdown_tabs,
        "results": results,
        "result_sections": result_sections,
        "show_result_sections": show_result_sections,
        "show_empty_content": show_empty_content,
        "no_data_message": empty_state_message,
        "selected_filters": {
            "year": selected_year,
            "period": selected_period,
            "faculty": selected_faculty,
        },
    }

    context = build_layout_context(request, "students")
    context.update(student_filter_context)
    context.update(
        {
            "page_title": student["name"],
            "student": student,
            "show_empty_content": show_empty_content,
            "no_data_message": empty_state_message,
            "selected_filters": student["selected_filters"],
            "back_to_students_url": back_to_students_url,
        }
    )
    return render(request, "dashboard/student_detail.html", context)


@login_required_except_domains()
def student_transcript(request, slug):
    """Render a comprehensive transcript page showing all student results with consistent styling."""

    try:
        student_record = get_object_or_404(
            Student.objects.prefetch_related(
                "registrations__course_results__course",
                "registrations__programme__department__faculty",
                "registrations__period",
            ),
            registration_number__iexact=slug,
        )
        all_registrations = list(student_record.registrations.all())
        timeline = build_student_timeline(
            [registration for registration in all_registrations if _registration_has_course_results(registration)]
        )
        transcript_results = []
        for group in timeline["groups"]:
            for row in group["results"]:
                mark_value = row["mark_value"]
                grade = "F"
                if mark_value is not None:
                    if mark_value >= 75:
                        grade = "1"
                    elif mark_value >= 65:
                        grade = "2.1"
                    elif mark_value >= 60:
                        grade = "2.2"
                    elif mark_value >= 50:
                        grade = "3"

                transcript_results.append(
                    {
                        "academic_year": row["academic_year"],
                        "period": row["period"],
                        "semester": row["semester_label"],
                        "academic_level_label": row["academic_level_label"],
                        "period_name": row["period_name"],
                        "faculty": row["registration"].programme.department.faculty.name if row["registration"].programme and row["registration"].programme.department and row["registration"].programme.department.faculty else "Unknown",
                        "programme": row["registration"].programme.normalized_name if row["registration"].programme else "Unknown",
                        "course_code": row["course_code"],
                        "course_name": row["course_name"],
                        "course_display_name": row["course_display_name"],
                        "mark": row["mark"],
                        "mark_value": mark_value if mark_value is not None else "--",
                        "grade": grade,
                        "decision": "P" if row["is_pass"] else "F",
                        "status": "Pass" if row["is_pass"] else "Fail",
                        "is_failing": row["is_failing"],
                        "attempt_number": row["attempt_number"],
                        "attempt_tags": row["attempt_tags"],
                    }
                )

        summary = build_transcript_summary(timeline["groups"])
        student_programme = latest_registration.programme.normalized_name if (latest_registration := (all_registrations[-1] if all_registrations else None)) and latest_registration.programme else "N/A"
        student_faculty = (
            latest_registration.programme.department.faculty.name
            if latest_registration and latest_registration.programme and latest_registration.programme.department and latest_registration.programme.department.faculty
            else "N/A"
        )

        context = build_layout_context(request, "Student Transcript")
        context.update(
            {
                "page_title": f"Transcript - {student_record.first_names} {student_record.surname}",
                "back_to_students_url": _student_list_back_url(request),
                "student": {
                    "name": f"{student_record.first_names} {student_record.surname}",
                    "student_number": student_record.registration_number,
                    "programme": student_programme,
                    "faculty": student_faculty,
                },
                "transcript_results": transcript_results,
                "summary": summary,
            }
        )
        
        return render(request, "dashboard/student_transcript.html", context)
        
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in student_transcript for slug {slug}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Return error page with actual error message for debugging
        context = build_layout_context(request, "Error")
        context.update({
            "page_title": "Transcript Error",
            "error_message": f"Error: {str(e)} (Type: {type(e).__name__})",
            "back_to_students_url": _student_list_back_url(request),
        })
        return render(request, "dashboard/student_transcript.html", context)


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


def _format_audit_detail(action, detail):
    if not detail:
        return ""
    if action == AuditLog.ACTION_AI_PROVIDER_CHANGED:
        return f"{detail.get('old', '?')} → {detail.get('new', '?')}"
    if action == AuditLog.ACTION_LOGIN_FAILED:
        return detail.get("reason", "")
    return ", ".join(f"{k}: {v}" for k, v in detail.items())


def _build_audit_log_context(request):
    from datetime import datetime
    search_q = request.GET.get("audit_q", "").strip()
    action_filter = request.GET.get("audit_action", "").strip()
    date_from_raw = request.GET.get("audit_from", "").strip()
    date_to_raw = request.GET.get("audit_to", "").strip()

    qs = AuditLog.objects.all()
    if search_q:
        qs = qs.filter(
            Q(actor_email__icontains=search_q) | Q(target_email__icontains=search_q)
        )
    if action_filter:
        qs = qs.filter(action=action_filter)

    date_from = date_to = None
    try:
        if date_from_raw:
            date_from = datetime.strptime(date_from_raw, "%Y-%m-%d").date()
            qs = qs.filter(timestamp__date__gte=date_from)
    except ValueError:
        date_from_raw = ""
    try:
        if date_to_raw:
            date_to = datetime.strptime(date_to_raw, "%Y-%m-%d").date()
            qs = qs.filter(timestamp__date__lte=date_to)
    except ValueError:
        date_to_raw = ""

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("audit_page"))
    page_start = max(page_obj.number - 2, 1)
    page_end = min(page_obj.number + 2, paginator.num_pages)

    entries = [
        {
            "timestamp": entry.timestamp,
            "actor_email": entry.actor_email or "—",
            "action_label": entry.get_action_display(),
            "action": entry.action,
            "tone": AuditLog.ACTION_TONE.get(entry.action, "neutral"),
            "target_email": entry.target_email or "—",
            "detail": _format_audit_detail(entry.action, entry.detail),
            "ip_address": entry.ip_address or "—",
        }
        for entry in page_obj.object_list
    ]

    has_filter = bool(search_q or action_filter or date_from_raw or date_to_raw)
    return {
        "audit_entries": entries,
        "audit_page_obj": page_obj,
        "audit_page_numbers": range(page_start, page_end + 1),
        "audit_search_query": search_q,
        "audit_action_filter": action_filter,
        "audit_date_from": date_from_raw,
        "audit_date_to": date_to_raw,
        "audit_has_filter": has_filter,
        "audit_action_choices": AuditLog.ACTION_CHOICES,
    }


@platform_admin_required
def system_management_view(request):
    """Render the admin-only system workspace for user access and platform controls."""

    user_model = get_user_model()
    redirect_target = request.POST.get("next") or reverse("dashboard:system-management")
    show_user_modal = False

    if request.method == "POST":
        action = request.POST.get("action", "create-user")

        if action == "set-ai-provider":
            _AI_VALID_PROVIDERS = {"google", "openai", "rules", "auto"}
            chosen = request.POST.get("provider", "").strip().lower()
            if chosen in _AI_VALID_PROVIDERS:
                old_provider = PlatformSetting.get_value("ai_provider", "auto") or "auto"
                PlatformSetting.set_value("ai_provider", chosen)
                _labels = {"google": "Google Gemini", "openai": "OpenAI", "rules": "Rule-based engine", "auto": "Auto"}
                messages.success(request, f"AI insights provider set to {_labels[chosen]}.")
                AuditLog.record(
                    AuditLog.ACTION_AI_PROVIDER_CHANGED,
                    detail={"old": old_provider, "new": chosen},
                    request=request,
                )
            else:
                messages.error(request, "Invalid AI provider selection.")
            return redirect(redirect_target)

        if action == "create-user":
            user_form = SystemManagementUserForm(request.POST)
            if user_form.is_valid():
                created_user = user_form.save()
                messages.success(request, f"{created_user.email} was added successfully.")
                AuditLog.record(
                    AuditLog.ACTION_USER_CREATED,
                    target_email=created_user.email,
                    request=request,
                )
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
                    AuditLog.record(
                        AuditLog.ACTION_USER_ACTIVATED if managed_user.is_active else AuditLog.ACTION_USER_DEACTIVATED,
                        target_email=managed_user.email,
                        request=request,
                    )
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
                    AuditLog.record(
                        AuditLog.ACTION_LOCKOUT_CLEARED,
                        target_email=managed_user.email,
                        request=request,
                    )
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

    _on_users_tab = request.GET.get("tab", "users") != "audit" and request.GET.get("tab") != "ai"
    if _on_users_tab or show_user_modal:
        lockout_records = get_active_user_lockout_records()
        user_rows = build_system_user_rows(managed_users, lockout_records, request.user)
    else:
        user_rows = []

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
            "active_tab": request.GET.get("tab", "users"),
            "ai_provider": PlatformSetting.get_value("ai_provider", "auto") or "auto",
            "ai_google_available": bool(getattr(django_settings, "GOOGLE_API_KEY", "")),
            "ai_openai_available": bool(getattr(django_settings, "OPENAI_API_KEY", "")),
            "ai_insights_enabled": bool(getattr(django_settings, "AI_INSIGHTS_ENABLED", False)),
            **(
                _build_audit_log_context(request)
                if request.GET.get("tab") == "audit"
                else {
                    "audit_entries": [],
                    "audit_page_obj": None,
                    "audit_page_numbers": range(0),
                    "audit_search_query": "",
                    "audit_action_filter": "",
                    "audit_date_from": "",
                    "audit_date_to": "",
                    "audit_has_filter": False,
                    "audit_action_choices": AuditLog.ACTION_CHOICES,
                }
            ),
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



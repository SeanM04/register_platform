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
    
    # Extract year and remove it completely
    year_match = re.search(r"(20\d{2})", period_name)
    if year_match:
        text = period_name.replace(year_match.group(0), "").strip()
    else:
        text = period_name
    
    # Clean up remaining text
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


def normalize_gender_key(gender):
    """Normalize free-text gender values into stable dashboard buckets."""

    text = str(gender or "").strip().lower()
    if text == "male":
        return "male"
    if text == "female":
        return "female"
    return "unspecified"


def build_filters(request):
    """Build shared topbar filter metadata from request query parameters."""

    selected_year = request.GET.get("year", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_faculty = request.GET.get("faculty", "").strip()

    periods = list(AcademicPeriod.objects.order_by("name").values("name"))
    years = sorted({extract_period_year(period["name"]) for period in periods if extract_period_year(period["name"])}, reverse=True)
    
    # Filter periods by selected year and create options with display labels
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
    """Build shared sidebar and filter context for dashboard templates."""

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
    """Delegate programme queryset shaping to the feature package for compatibility."""

    from .programmes.services import get_programmes_queryset as feature_get_programmes_queryset

    return feature_get_programmes_queryset(request, search_query)


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
    """Assemble the live operational signals and recommendation content for Insights."""

    from .insights.services import build_insights_dashboard_data as feature_build_insights_dashboard_data

    return feature_build_insights_dashboard_data(request)


@login_required_except_domains()
def dashboard_home(request):
    """Delegate home-page rendering to the overview feature package."""

    from .overview.views import dashboard_home as feature_dashboard_home

    return feature_dashboard_home(request)


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
    """Delegate home metric hydration to the overview feature package."""

    from .overview.views import dashboard_home_metrics as feature_dashboard_home_metrics

    return feature_dashboard_home_metrics(request)


@ajax_login_required
@require_GET
def programme_metrics(request):
    """Delegate programme metrics JSON to the feature package for compatibility."""

    from .programmes.views import programme_metrics as feature_programme_metrics

    return feature_programme_metrics(request)



"""Views for the story-first landing dashboard."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_overview_card_narratives_result
from .presenters import build_overview_shell_context
from .services import build_overview_drilldown_data, get_cached_overview_dashboard_data, get_home_summary_values, get_filtered_registrations


@login_required_except_domains()
def dashboard_home(request):
    """Render the landing-page dashboard shown immediately after login."""

    return render(request, "dashboard/home.html", build_overview_shell_context(request))


@ajax_login_required
@require_GET
def dashboard_home_metrics(request):
    """Return landing-page headline metrics as JSON."""

    return JsonResponse({"metrics": get_home_summary_values(request)})


@ajax_login_required
@require_GET
def dashboard_home_payload(request):
    """Return the heavy landing-page chart and route-card payload after first paint."""

    overview_data = get_cached_overview_dashboard_data(request)
    return JsonResponse(
        {
            "summary_cards": overview_data["summary_cards"],
            "outcome_rows": overview_data["outcome_rows"],
            "risk_distribution_rows": overview_data["risk_distribution_rows"],
            "faculty_load_rows": overview_data["faculty_load_rows"],
            "progress_rows": overview_data["progress_rows"],
            "action_cards": overview_data["action_cards"],
        }
    )


@ajax_login_required
@require_GET
def dashboard_home_narratives(request):
    """Return the optional AI/rules overview narrative payload separately from the charts."""

    overview_data = get_cached_overview_dashboard_data(request)
    return JsonResponse(get_overview_card_narratives_result(overview_data))


@ajax_login_required
@require_GET
def dashboard_home_drilldown(request):
    """Return on-demand student rows for the requested landing-page chart bucket."""

    chart_key = str(request.GET.get("chart", "")).strip().lower()
    bucket_key = str(request.GET.get("bucket", "")).strip()
    if not chart_key or not bucket_key:
        return JsonResponse({"error": "Both chart and bucket are required."}, status=400)

    # Handle hierarchical drilldown for faculty load
    if chart_key == "faculty_load":
        from .services import _build_faculty_drilldown_payload
        try:
            page = int(request.GET.get("page", 1))
            page_size = int(request.GET.get("page_size", 10))
        except (TypeError, ValueError):
            page = 1
            page_size = 10
        
        payload = _build_faculty_drilldown_payload(request, list(get_filtered_registrations(request)), bucket_key, page, page_size)
        return JsonResponse(payload)

    try:
        payload = build_overview_drilldown_data(request, chart_key, bucket_key)
        return JsonResponse(payload)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

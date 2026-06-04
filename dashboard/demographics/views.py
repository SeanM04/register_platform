"""Views for the demographics dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_demographic_card_narratives_result
from .presenters import DEMOGRAPHIC_SHELL_NOTES, DEMOGRAPHIC_SUMMARY_CARD_NOTES, build_demographic_shell_context
from .constants import DEMOGRAPHIC_SUMMARY_CARD_SPECS
from .services import (
    get_cached_demographic_data,
    get_cached_demographic_fast_metrics,
)
from ..views import build_summary_cards


@login_required_except_domains()
def demographic_view(request):
    """Render the fast shell for the demographics dashboard page."""

    search_query = request.GET.get("q", "").strip()
    context = build_demographic_shell_context(request, search_query)
    return render(request, "dashboard/demographic.html", context)


@ajax_login_required
@require_GET
def demographic_metrics(request):
    """Return demographic KPI card values via fast DB aggregates for first-paint hydration."""

    search_query = request.GET.get("q", "").strip()
    metrics = get_cached_demographic_fast_metrics(request, search_query)
    return JsonResponse({
        "metrics": metrics,
        "summary_cards": build_summary_cards(DEMOGRAPHIC_SUMMARY_CARD_SPECS, metrics, DEMOGRAPHIC_SUMMARY_CARD_NOTES),
    })


@ajax_login_required
@require_GET
def demographic_payload(request):
    """Return the heavy demographic chart and register payload after first paint."""

    search_query = request.GET.get("q", "").strip()
    demographic_data = get_cached_demographic_data(request, search_query)
    metrics = demographic_data["summary_metrics"]
    return JsonResponse(
        {
            "metrics": metrics,
            "summary_cards": build_summary_cards(DEMOGRAPHIC_SUMMARY_CARD_SPECS, metrics, DEMOGRAPHIC_SUMMARY_CARD_NOTES),
            "gender_rows": demographic_data["gender_rows"],
            "location_rows": demographic_data["location_rows"],
            "location_mix_rows": demographic_data["location_mix_rows"],
            "location_map_rows": demographic_data["location_map_rows"],
            "location_map_meta": demographic_data["location_map_meta"],
            "programme_rows": demographic_data["programme_rows"],
            "programme_gender_rows": demographic_data.get("programme_gender_rows", []),
            "year_distribution_rows": demographic_data.get("year_distribution_rows", []),
            "age_distribution_rows": demographic_data.get("age_distribution_rows", []),
            "register_meta": {
                "visible_count": len(demographic_data["programme_rows"]),
            },
        }
    )


@ajax_login_required
@require_GET
def demographic_narratives(request):
    """Return the optional AI/rules narrative payload separately from the charts."""

    search_query = request.GET.get("q", "").strip()
    demographic_data = get_cached_demographic_data(request, search_query)
    return JsonResponse(get_demographic_card_narratives_result(demographic_data))


@ajax_login_required
@require_GET
def demographic_drilldown(request):
    """Return drilldown data for demographic charts."""
    from .drilldown_services import build_demographic_drilldown_data

    chart_key = request.GET.get("chart")
    bucket_key = request.GET.get("bucket")

    if not chart_key or not bucket_key:
        return JsonResponse({"error": "Missing required parameters: chart and bucket"}, status=400)

    try:
        page = max(int(request.GET.get("page", 1)), 1)
        page_size = min(max(int(request.GET.get("page_size", 10)), 1), 100)
    except (TypeError, ValueError):
        page, page_size = 1, 10

    try:
        drilldown_data = build_demographic_drilldown_data(
            request, chart_key, bucket_key, page, page_size
        )
        return JsonResponse(drilldown_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

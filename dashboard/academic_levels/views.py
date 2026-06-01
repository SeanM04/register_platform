"""Views for the academic-level dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_academic_level_card_narratives_result
from .presenters import build_academic_level_shell_context
from .services import (
    build_academic_level_drilldown_data,
    get_cached_academic_level_dashboard_data,
    get_cached_academic_level_fast_metrics,
    get_academic_level_summary_values,
)


@login_required_except_domains()
def academic_level_view(request):
    """Render the fast shell for the academic-level dashboard page."""

    search_query = request.GET.get("q", "").strip()
    return render(
        request,
        "dashboard/academic_level.html",
        build_academic_level_shell_context(request, search_query),
    )


@ajax_login_required
@require_GET
def academic_level_metrics(request):
    """Return academic-level dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    summary_snapshot = get_cached_academic_level_fast_metrics(request, search_query)
    return JsonResponse(summary_snapshot)


@ajax_login_required
@require_GET
def academic_level_payload(request):
    """Return the heavy academic-level chart, register, and narrative payload after first paint."""

    search_query = request.GET.get("q", "").strip()
    academic_level_data = get_cached_academic_level_dashboard_data(request, search_query)
    narrative_result = get_academic_level_card_narratives_result(academic_level_data)

    return JsonResponse(
        {
            "metrics": get_academic_level_summary_values(
                request, search_query, academic_level_data
            ),
            "level_rows": academic_level_data["level_rows"],
            "level_chart_rows": academic_level_data["level_chart_rows"],
            "gender_performance_rows": academic_level_data["gender_performance_rows"],
            "programme_performance_rows": academic_level_data["programme_performance_rows"],
            "card_narratives": narrative_result["card_narratives"],
            "diagnostics": narrative_result["diagnostics"],
        }
    )


@ajax_login_required
@require_GET
def academic_level_drilldown(request):
    """Return modal drill-down data for academic-level charts."""

    chart_key = request.GET.get("chart", "").strip()
    bucket_key = request.GET.get("bucket", "").strip()
    search_query = request.GET.get("q", "").strip()
    if not chart_key or not bucket_key:
        return JsonResponse({"error": "Both chart and bucket are required."}, status=400)

    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page = 1
        page_size = 10
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    try:
        return JsonResponse(
            build_academic_level_drilldown_data(
                request,
                chart_key,
                bucket_key,
                page=page,
                page_size=page_size,
                search_query=search_query,
            )
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

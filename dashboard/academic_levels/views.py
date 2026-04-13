"""Views for the academic-level dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_academic_level_card_narratives_result
from .presenters import build_academic_level_shell_context
from .services import (
    get_cached_academic_level_dashboard_data,
    get_cached_academic_level_summary_snapshot,
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
    summary_snapshot = get_cached_academic_level_summary_snapshot(request, search_query)
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
            "metrics": get_academic_level_summary_values(request, search_query, academic_level_data),
            "level_rows": academic_level_data["level_rows"],
            "level_chart_rows": academic_level_data["level_chart_rows"],
            "gender_performance_rows": academic_level_data["gender_performance_rows"],
            "programme_performance_rows": academic_level_data["programme_performance_rows"],
            "card_narratives": narrative_result["card_narratives"],
            "diagnostics": narrative_result["diagnostics"],
        }
    )

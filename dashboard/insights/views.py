"""Views for the insights dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required
from accounts.decorators import login_required_except_domains

from .ai_insights import get_insight_card_narratives
from .presenters import build_insight_shell_context
from .services import get_cached_insights_dashboard_data


@login_required_except_domains()
def insights_view(request):
    """Render the fast shell for the institutional insights dashboard."""

    return render(
        request,
        "dashboard/insights.html",
        build_insight_shell_context(request),
    )


@ajax_login_required
@require_GET
def insights_payload(request):
    """Return the heavy institutional insights payload after first paint."""

    insights_data = get_cached_insights_dashboard_data(request)
    return JsonResponse(
        {
            "summary_cards": insights_data["summary_cards"],
            "flagged_students": insights_data["flagged_students"],
            "flagged_total": insights_data["flagged_total"],
            "recommendations": insights_data["recommendations"],
            "faculty_load_rows": insights_data["faculty_load_rows"],
            "risk_distribution_rows": insights_data["risk_distribution_rows"],
            "faculty_pressure_rows": insights_data["faculty_pressure_rows"],
            "driver_rows": insights_data["driver_rows"],
            "confidence_rows": insights_data["confidence_rows"],
            "insight_card_narratives": get_insight_card_narratives(insights_data),
        }
    )

"""Views for the risk dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_risk_card_narratives
from .presenters import build_risk_shell_context
from .services import (
    get_cached_risk_dashboard_data,
    get_risk_summary_values,
    paginate_risk_rows,
)


@login_required_except_domains()
def risk_view(request):
    """Render the fast shell for the risk dashboard and action register."""

    search_query = request.GET.get("q", "").strip()
    return render(request, "dashboard/risk.html", build_risk_shell_context(request, search_query))


@ajax_login_required
@require_GET
def risk_metrics(request):
    """Return risk dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_risk_summary_values(request, search_query)})


@ajax_login_required
@require_GET
def risk_payload(request):
    """Return the heavy risk story, charts, and register payload after first paint."""

    search_query = request.GET.get("q", "").strip()
    risk_data = get_cached_risk_dashboard_data(request, search_query)
    page_data = paginate_risk_rows(risk_data["risk_rows"], request.GET.get("page"), page_size=20)

    return JsonResponse(
        {
            "metrics": get_risk_summary_values(request, search_query),
            "cohort_total_students": risk_data["total_students"],
            "watchlist_total_students": risk_data["at_risk_students"],
            "risk_distribution_rows": risk_data["risk_distribution_rows"],
            "risk_driver_rows": risk_data["risk_driver_rows"],
            "risk_level_rows": risk_data["risk_level_rows"],
            "risk_programme_rows": risk_data["risk_programme_rows"],
            "risk_card_narratives": get_risk_card_narratives(risk_data),
            "register": page_data,
        }
    )

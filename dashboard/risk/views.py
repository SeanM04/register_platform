"""Views for the risk dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .presenters import build_risk_page_context
from .services import build_risk_dashboard_data, get_risk_summary_values


@login_required_except_domains()
def risk_view(request):
    """Render the story-first risk dashboard and action register."""

    search_query = request.GET.get("q", "").strip()
    risk_data = build_risk_dashboard_data(request, search_query)
    context = build_risk_page_context(request, risk_data, search_query)
    return render(request, "dashboard/risk.html", context)


@ajax_login_required
@require_GET
def risk_metrics(request):
    """Return risk dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_risk_summary_values(request, search_query)})

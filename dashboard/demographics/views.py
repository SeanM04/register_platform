"""Views for the demographics dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .presenters import build_demographic_page_context
from .services import build_demographic_data, get_demographic_summary_values


@login_required_except_domains()
def demographic_view(request):
    """Render gender and place-of-birth demographic summaries and chart views."""

    search_query = request.GET.get("q", "").strip()
    demographic_data = build_demographic_data(request, search_query)
    context = build_demographic_page_context(request, demographic_data)
    return render(request, "dashboard/demographic.html", context)


@ajax_login_required
@require_GET
def demographic_metrics(request):
    """Return demographic dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_demographic_summary_values(request, search_query)})

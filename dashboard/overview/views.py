"""Views for the story-first landing dashboard."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .presenters import build_overview_page_context
from .services import build_overview_dashboard_data, get_home_summary_values


@login_required_except_domains()
def dashboard_home(request):
    """Render the landing-page dashboard shown immediately after login."""

    overview_data = build_overview_dashboard_data(request)
    context = build_overview_page_context(request, overview_data)
    return render(request, "dashboard/home.html", context)


@ajax_login_required
@require_GET
def dashboard_home_metrics(request):
    """Return landing-page headline metrics as JSON."""

    return JsonResponse({"metrics": get_home_summary_values(request)})

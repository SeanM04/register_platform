"""Views for the story-first programmes dashboard."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .presenters import build_programme_page_context
from .services import build_programme_dashboard_data, get_programme_summary_values


@login_required_except_domains()
def programme_view(request):
    """Render the story-first programmes dashboard and searchable register."""

    search_query = request.GET.get("q", "").strip()
    programme_data = build_programme_dashboard_data(request, search_query)
    context = build_programme_page_context(request, programme_data, search_query)
    return render(request, "dashboard/programme.html", context)


@ajax_login_required
@require_GET
def programme_metrics(request):
    """Return programme dashboard headline metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_programme_summary_values(request, search_query)})

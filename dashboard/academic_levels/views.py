"""Views for the academic-level dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .presenters import build_academic_level_page_context
from .services import build_academic_level_data, get_academic_level_summary_values


@login_required_except_domains()
def academic_level_view(request):
    """Render analytics grouped by academic year and semester level."""

    search_query = request.GET.get("q", "").strip()
    academic_level_data = build_academic_level_data(request, search_query)
    context = build_academic_level_page_context(request, search_query, academic_level_data)
    return render(request, "dashboard/academic_level.html", context)


@ajax_login_required
@require_GET
def academic_level_metrics(request):
    """Return academic-level dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_academic_level_summary_values(request, search_query)})

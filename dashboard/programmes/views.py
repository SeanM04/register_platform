"""Views for the story-first programmes dashboard."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_programme_card_narratives_result
from .presenters import build_programme_shell_context
from .services import build_programme_dashboard_data, get_programme_summary_values


@login_required_except_domains()
def programme_view(request):
    """Render the fast shell for the story-first programmes dashboard."""

    search_query = request.GET.get("q", "").strip()
    context = build_programme_shell_context(request, search_query)
    return render(request, "dashboard/programme.html", context)


@ajax_login_required
@require_GET
def programme_metrics(request):
    """Return programme dashboard headline metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_programme_summary_values(request, search_query)})


@ajax_login_required
@require_GET
def programme_payload(request):
    """Return the heavy programme chart and register payload after first paint."""

    search_query = request.GET.get("q", "").strip()
    programme_data = build_programme_dashboard_data(request, search_query)
    
        
    return JsonResponse(
        {
            "summary_cards": programme_data["summary_cards"],
            "top_load_rows": programme_data["top_load_rows"],
            "department_rows": programme_data["department_rows"],
            "low_pass_rows": programme_data["low_pass_rows"],
            "performance_rows": programme_data["performance_rows"],
            "programme_rows": programme_data["programme_rows"],
            "register_meta": programme_data["register_meta"],
        }
    )


@ajax_login_required
@require_GET
def programme_narratives(request):
    """Return the optional AI/rules narrative payload separately from the charts."""

    search_query = request.GET.get("q", "").strip()
    programme_data = build_programme_dashboard_data(request, search_query)
    return JsonResponse(get_programme_card_narratives_result(programme_data))


@ajax_login_required
@require_GET
def programme_drilldown(request):
    """Return on-demand student rows for the requested programme chart bucket."""

    from .services import build_programme_drilldown_data
    
    chart_key = str(request.GET.get("chart", "")).strip().lower()
    bucket_key = str(request.GET.get("bucket", "")).strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 10))
    
    if not chart_key or not bucket_key:
        return JsonResponse({"error": "Both chart and bucket are required."}, status=400)

    try:
        payload = build_programme_drilldown_data(request, chart_key, bucket_key, page, page_size)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    return JsonResponse(payload)

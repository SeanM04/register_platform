"""Views for the demographics dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_demographic_card_narratives
from .presenters import build_demographic_shell_context
from .services import build_demographic_data, get_demographic_summary_values


@login_required_except_domains()
def demographic_view(request):
    """Render the fast shell for the demographics dashboard page."""

    search_query = request.GET.get("q", "").strip()
    context = build_demographic_shell_context(request, search_query)
    return render(request, "dashboard/demographic.html", context)


@ajax_login_required
@require_GET
def demographic_metrics(request):
    """Return demographic dashboard summary metrics as JSON."""

    search_query = request.GET.get("q", "").strip()
    return JsonResponse({"metrics": get_demographic_summary_values(request, search_query)})


@ajax_login_required
@require_GET
def demographic_payload(request):
    """Return the heavy demographic chart and register payload after first paint."""

    search_query = request.GET.get("q", "").strip()
    demographic_data = build_demographic_data(request, search_query)
    return JsonResponse(
        {
            "metrics": demographic_data["summary_metrics"],
            "gender_rows": demographic_data["gender_rows"],
            "location_rows": demographic_data["location_rows"],
            "location_mix_rows": demographic_data["location_mix_rows"],
            "location_map_rows": demographic_data["location_map_rows"],
            "location_map_meta": demographic_data["location_map_meta"],
            "programme_rows": demographic_data["programme_rows"],
            "register_meta": {
                "visible_count": len(demographic_data["programme_rows"]),
            },
        }
    )


@ajax_login_required
@require_GET
def demographic_narratives(request):
    """Return the optional AI/rules narrative payload separately from the charts."""

    search_query = request.GET.get("q", "").strip()
    demographic_data = build_demographic_data(request, search_query)
    return JsonResponse({"card_narratives": get_demographic_card_narratives(demographic_data)})

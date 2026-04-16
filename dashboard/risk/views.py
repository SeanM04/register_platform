"""Views for the risk dashboard feature."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.decorators import ajax_login_required, login_required_except_domains

from .ai_insights import get_risk_card_narratives
from .presenters import build_risk_shell_context
from .services import (
    build_risk_drilldown_payload,
    build_student_risk_profiles,
    get_cached_risk_dashboard_data,
    get_risk_summary_values,
    paginate_risk_rows,
)


@login_required_except_domains()
def risk_view(request):
    """Render the fast shell for the risk dashboard and action register."""

    search_query = request.GET.get("q", "").strip()
    return render(request, "dashboard/risk.html", build_risk_shell_context(request, search_query))


@login_required_except_domains()
def risk_band_drilldown(request, risk_band):
    """Render drill-down page for a specific risk band."""

    search_query = request.GET.get("q", "").strip()
    risk_profiles = build_student_risk_profiles(request, search_query)

    # Filter profiles by risk score ranges to match graph counts
    def match_risk_score(score, band_key):
        score = int(score or 0)
        if band_key == "low":
            return score <= 1
        elif band_key == "moderate":
            return 2 <= score <= 3
        elif band_key == "high":
            return 4 <= score <= 5
        elif band_key == "critical":
            return score >= 6
        return False

    filtered_students = [p for p in risk_profiles if match_risk_score(p.get("risk_score", 0), risk_band.lower())]

    # Get band label for display
    band_labels = {
        "low": "Low Risk (0-1)",
        "moderate": "Medium Risk (2-3)",
        "high": "High Risk (4-5)",
        "critical": "Critical (6+)",
    }

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(filtered_students, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = build_risk_shell_context(request, search_query)
    context.update({
        "page_title": f"Risk Band: {band_labels.get(risk_band, risk_band)}",
        "risk_band": risk_band,
        "risk_band_label": band_labels.get(risk_band, risk_band),
        "students": page_obj,
        "total_students": len(filtered_students),
    })

    return render(request, "dashboard/risk_band_drilldown.html", context)


@login_required_except_domains()
def risk_level_drilldown(request, academic_level):
    """Render drill-down page for a specific academic level."""

    search_query = request.GET.get("q", "").strip()
    risk_profiles = build_student_risk_profiles(request, search_query)

    # Filter profiles by academic level
    filtered_students = [p for p in risk_profiles if p["academic_level"] == academic_level]

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(filtered_students, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = build_risk_shell_context(request, search_query)
    context.update({
        "page_title": f"Academic Level: {academic_level}",
        "academic_level": academic_level,
        "students": page_obj,
        "total_students": len(filtered_students),
    })

    return render(request, "dashboard/risk_level_drilldown.html", context)


@login_required_except_domains()
def risk_driver_drilldown(request, risk_driver):
    """Render drill-down page for a specific risk driver."""

    search_query = request.GET.get("q", "").strip()
    risk_profiles = build_student_risk_profiles(request, search_query)

    # Filter profiles by risk driver tag
    filtered_students = [p for p in risk_profiles if risk_driver in p.get("risk_driver_tags", [])]

    # Get driver label for display
    from .constants import RISK_DRIVER_LABELS
    driver_label = RISK_DRIVER_LABELS.get(risk_driver, risk_driver.replace("_", " ").title())

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(filtered_students, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = build_risk_shell_context(request, search_query)
    context.update({
        "page_title": f"Risk Driver: {driver_label}",
        "risk_driver": risk_driver,
        "risk_driver_label": driver_label,
        "students": page_obj,
        "total_students": len(filtered_students),
    })

    return render(request, "dashboard/risk_driver_drilldown.html", context)


@login_required_except_domains()
def risk_programme_drilldown(request, programme):
    """Render drill-down page for a specific programme."""

    search_query = request.GET.get("q", "").strip()
    risk_profiles = build_student_risk_profiles(request, search_query)

    # Filter profiles by programme
    filtered_students = [p for p in risk_profiles if p["programme"] == programme]

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(filtered_students, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = build_risk_shell_context(request, search_query)
    context.update({
        "page_title": f"Programme: {programme}",
        "programme": programme,
        "students": page_obj,
        "total_students": len(filtered_students),
    })

    return render(request, "dashboard/risk_programme_drilldown.html", context)


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


@ajax_login_required
@require_GET
def risk_drilldown_payload(request):
    """Return modal drill-down rows for an interactive risk chart selection."""

    search_query = request.GET.get("q", "").strip()
    chart_key = request.GET.get("chart", "").strip()
    bucket_key = request.GET.get("bucket", "").strip()

    try:
        page_size = int(request.GET.get("page_size") or 10)
    except (TypeError, ValueError):
        page_size = 10

    payload = build_risk_drilldown_payload(
        request,
        chart_key,
        bucket_key,
        search_query=search_query,
        page_number=request.GET.get("page"),
        page_size=max(1, min(page_size, 100)),
    )
    if payload is None:
        return JsonResponse({"detail": "Unknown drill-down selection."}, status=400)

    return JsonResponse(payload)

"""Views for the insights dashboard feature."""

from django.shortcuts import render

from accounts.decorators import login_required_except_domains

from .presenters import build_insight_page_context
from .services import build_insights_dashboard_data


@login_required_except_domains()
def insights_view(request):
    """Render the story-first institutional insights dashboard."""

    insights_data = build_insights_dashboard_data(request)
    context = build_insight_page_context(request, insights_data)
    return render(request, "dashboard/insights.html", context)

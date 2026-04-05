"""Presentation helpers for the insights dashboard views."""

from ..views import build_layout_context
from .ai_insights import get_insight_card_narratives
from .constants import INSIGHTS_ACTIVE_KEY, INSIGHTS_PAGE_TITLE


def build_insight_page_context(request, insights_data):
    """Build the template context for the insights dashboard page."""

    context = build_layout_context(request, INSIGHTS_ACTIVE_KEY)
    context.update(
        {
            "page_title": INSIGHTS_PAGE_TITLE,
            "summary_cards": insights_data["summary_cards"],
            "insight_summary_cards": insights_data["summary_cards"],
            "insight_scope_pills": insights_data["scope_pills"],
            "flagged_students": insights_data["flagged_students"],
            "flagged_total": insights_data["flagged_total"],
            "recommendations": insights_data["recommendations"],
            "faculty_load_rows": insights_data["faculty_load_rows"],
            "risk_distribution_rows": insights_data["risk_distribution_rows"],
            "faculty_pressure_rows": insights_data["faculty_pressure_rows"],
            "driver_rows": insights_data["driver_rows"],
            "confidence_rows": insights_data["confidence_rows"],
            "insight_card_narratives": get_insight_card_narratives(insights_data),
        }
    )
    return context

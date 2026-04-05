"""Presentation helpers for the story-first landing dashboard."""

from ..views import build_layout_context
from .ai_insights import get_overview_card_narratives
from .constants import OVERVIEW_ACTIVE_KEY, OVERVIEW_PAGE_TITLE


def build_overview_page_context(request, overview_data):
    """Build the template context for the landing-page overview dashboard."""

    context = build_layout_context(request, OVERVIEW_ACTIVE_KEY)
    context.update(
        {
            "page_title": OVERVIEW_PAGE_TITLE,
            "summary_cards": overview_data["summary_cards"],
            "scope_pills": overview_data["scope_pills"],
            "outcome_rows": overview_data["outcome_rows"],
            "risk_distribution_rows": overview_data["risk_distribution_rows"],
            "faculty_load_rows": overview_data["faculty_load_rows"],
            "progress_rows": overview_data["progress_rows"],
            "overview_card_narratives": get_overview_card_narratives(overview_data),
            "action_cards": overview_data["action_cards"],
        }
    )
    return context

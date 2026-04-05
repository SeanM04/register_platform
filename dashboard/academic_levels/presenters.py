"""Presentation helpers for the academic-level dashboard views."""

from ..views import build_layout_context, build_summary_cards

from .ai_insights import get_academic_level_card_narratives
from .constants import (
    ACADEMIC_LEVEL_ACTIVE_KEY,
    ACADEMIC_LEVEL_PAGE_TITLE,
    ACADEMIC_LEVEL_SUMMARY_CARD_SPECS,
)


def build_academic_level_page_context(request, search_query, academic_level_data):
    """Build the template context for the academic-level dashboard page."""

    context = build_layout_context(request, ACADEMIC_LEVEL_ACTIVE_KEY)
    context.update(
        {
            "page_title": ACADEMIC_LEVEL_PAGE_TITLE,
            "search_query": search_query,
            "summary_cards": build_summary_cards(ACADEMIC_LEVEL_SUMMARY_CARD_SPECS),
            "level_rows": academic_level_data["level_rows"],
            "level_chart_rows": academic_level_data["level_chart_rows"],
            "gender_performance_rows": academic_level_data["gender_performance_rows"],
            "programme_performance_rows": academic_level_data["programme_performance_rows"],
            "academic_level_card_narratives": get_academic_level_card_narratives(academic_level_data),
        }
    )
    return context

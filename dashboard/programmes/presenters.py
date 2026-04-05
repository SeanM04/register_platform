"""Presentation helpers for the story-first programmes dashboard."""

from ..views import build_layout_context
from .ai_insights import get_programme_card_narratives
from .constants import PROGRAMMES_ACTIVE_KEY, PROGRAMMES_PAGE_TITLE


def build_programme_page_context(request, programme_data, search_query=""):
    """Build the template context for the programme dashboard page."""

    context = build_layout_context(request, PROGRAMMES_ACTIVE_KEY)
    context.update(
        {
            "page_title": PROGRAMMES_PAGE_TITLE,
            "search_query": search_query,
            "summary_cards": programme_data["summary_cards"],
            "scope_pills": programme_data["scope_pills"],
            "programme_rows": programme_data["programme_rows"],
            "top_load_rows": programme_data["top_load_rows"],
            "department_rows": programme_data["department_rows"],
            "low_pass_rows": programme_data["low_pass_rows"],
            "performance_rows": programme_data["performance_rows"],
            "programme_card_narratives": get_programme_card_narratives(programme_data),
        }
    )
    return context

"""Presentation helpers for the academic-level dashboard views."""

from ..views import build_layout_context, build_summary_cards

from .ai_insights import get_academic_level_card_narratives_result
from .constants import (
    ACADEMIC_LEVEL_ACTIVE_KEY,
    ACADEMIC_LEVEL_PAGE_TITLE,
    ACADEMIC_LEVEL_SUMMARY_CARD_SPECS,
)


ACADEMIC_LEVEL_SHELL_NOTES = {
    "levels": "Loading the visible academic levels for the selected scope.",
    "registrations": "Loading the registration footprint across the visible levels.",
    "students": "Loading the unique student count across the visible levels.",
    "average_pass_rate": "Loading the average pass rate across the visible levels.",
}


def build_academic_level_shell_context(request, search_query):
    """Build a lightweight first-paint context for the academic-level dashboard page."""

    context = build_layout_context(request, ACADEMIC_LEVEL_ACTIVE_KEY)
    context.update(
        {
            "page_title": ACADEMIC_LEVEL_PAGE_TITLE,
            "search_query": search_query,
            "summary_cards": [
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "tone": spec["tone"],
                    "value": "--",
                    "note": ACADEMIC_LEVEL_SHELL_NOTES.get(spec["key"], "Loading current academic-level context."),
                }
                for spec in ACADEMIC_LEVEL_SUMMARY_CARD_SPECS
            ],
        }
    )
    return context


def build_academic_level_page_context(request, search_query, academic_level_data):
    """Build the template context for the academic-level dashboard page."""

    narrative_result = get_academic_level_card_narratives_result(academic_level_data)
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
            "academic_level_card_narratives": narrative_result["card_narratives"],
            "academic_level_narrative_diagnostics": narrative_result["diagnostics"],
        }
    )
    return context

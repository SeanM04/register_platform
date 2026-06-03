"""Presentation helpers for the demographics dashboard views."""

from ..views import build_layout_context, build_summary_cards

from .ai_insights import get_demographic_card_narratives
from .constants import DEMOGRAPHICS_ACTIVE_KEY, DEMOGRAPHICS_PAGE_TITLE, DEMOGRAPHIC_SUMMARY_CARD_SPECS


DEMOGRAPHIC_SHELL_NOTES = {
    "students": "Loading the visible student count for the selected scope.",
    "male": "Loading the male student distribution for the selected scope.",
    "female": "Loading the female student distribution for the selected scope.",
    "birth_locations": "Loading the birth location distribution for the selected scope.",
}

DEMOGRAPHIC_SUMMARY_CARD_NOTES = {
    "students": "Unique students currently visible in scope.",
    "male": "Male student count in the current scope.",
    "female": "Female student count in the current scope.",
    "birth_locations": "Distinct birth locations represented in scope.",
}


def build_demographic_shell_context(request, search_query=""):
    """Build a lightweight first-paint context for the demographic dashboard page."""

    context = build_layout_context(request, DEMOGRAPHICS_ACTIVE_KEY)
    context.update(
        {
            "page_title": DEMOGRAPHICS_PAGE_TITLE,
            "search_query": search_query,
            "summary_cards": [
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "tone": spec["tone"],
                    "value": "--",
                    "note": DEMOGRAPHIC_SHELL_NOTES.get(spec["key"], "Loading current demographic context."),
                }
                for spec in DEMOGRAPHIC_SUMMARY_CARD_SPECS
            ],
        }
    )
    return context


def build_demographic_page_context(request, demographic_data):
    """Build the template context for the demographics dashboard page."""

    context = build_layout_context(request, DEMOGRAPHICS_ACTIVE_KEY)
    context.update(
        {
            "page_title": DEMOGRAPHICS_PAGE_TITLE,
            "summary_cards": build_summary_cards(
                DEMOGRAPHIC_SUMMARY_CARD_SPECS,
                demographic_data.get("summary_metrics", {}),
                DEMOGRAPHIC_SUMMARY_CARD_NOTES,
            ),
            "gender_rows": demographic_data["gender_rows"],
            "location_rows": demographic_data["location_rows"],
            "location_mix_rows": demographic_data["location_mix_rows"],
            "location_map_rows": demographic_data["location_map_rows"],
            "location_map_meta": demographic_data["location_map_meta"],
            "programme_rows": demographic_data["programme_rows"],
            "programme_gender_rows": demographic_data["programme_gender_rows"],
            "year_distribution_rows": demographic_data["year_distribution_rows"],
            "age_distribution_rows": demographic_data["age_distribution_rows"],
            "demographic_card_narratives": get_demographic_card_narratives(demographic_data),
        }
    )
    return context

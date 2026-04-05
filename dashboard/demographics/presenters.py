"""Presentation helpers for the demographics dashboard views."""

from ..views import build_layout_context, build_summary_cards

from .ai_insights import get_demographic_card_narratives
from .constants import DEMOGRAPHICS_ACTIVE_KEY, DEMOGRAPHICS_PAGE_TITLE, DEMOGRAPHIC_SUMMARY_CARD_SPECS


def build_demographic_page_context(request, demographic_data):
    """Build the template context for the demographics dashboard page."""

    context = build_layout_context(request, DEMOGRAPHICS_ACTIVE_KEY)
    context.update(
        {
            "page_title": DEMOGRAPHICS_PAGE_TITLE,
            "summary_cards": build_summary_cards(DEMOGRAPHIC_SUMMARY_CARD_SPECS),
            "gender_rows": demographic_data["gender_rows"],
            "location_rows": demographic_data["location_rows"],
            "location_mix_rows": demographic_data["location_mix_rows"],
            "location_map_rows": demographic_data["location_map_rows"],
            "location_map_meta": demographic_data["location_map_meta"],
            "programme_rows": demographic_data["programme_rows"],
            "demographic_card_narratives": get_demographic_card_narratives(demographic_data),
        }
    )
    return context

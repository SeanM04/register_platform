"""Presentation helpers for the risk dashboard views."""

from django.core.paginator import Paginator

from ..views import build_layout_context, build_summary_cards
from .ai_insights import get_risk_card_narratives
from .constants import RISK_ACTIVE_KEY, RISK_PAGE_TITLE, RISK_SUMMARY_CARD_SPECS


RISK_SHELL_NOTES = {
    "at_risk_students": "Loading the visible watchlist size for the selected scope.",
    "high_risk": "Loading the count of high-priority students in the current watchlist.",
    "medium_risk": "Loading the count of medium-priority students in the current watchlist.",
    "multi_fail": "Loading the students with 2 or more failed modules.",
}

RISK_SUMMARY_CARD_NOTES = {
    "at_risk_students": "Students currently classified as medium or high risk.",
    "high_risk": "Students in the high-priority risk band.",
    "medium_risk": "Students in the medium-priority risk band.",
    "multi_fail": "Students with two or more failed modules.",
}


def build_risk_shell_context(request, search_query=""):
    """Build a lightweight first-paint context for the risk dashboard page."""

    context = build_layout_context(request, RISK_ACTIVE_KEY)
    context.update(
        {
            "page_title": RISK_PAGE_TITLE,
            "search_query": search_query,
            "summary_cards": [
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "tone": spec["tone"],
                    "value": "--",
                    "note": RISK_SHELL_NOTES.get(spec["key"], "Loading current risk context."),
                }
                for spec in RISK_SUMMARY_CARD_SPECS
            ],
        }
    )
    return context


def build_risk_page_context(request, risk_data, search_query=""):
    """Build the template context for the risk dashboard page."""

    paginator = Paginator(risk_data["risk_rows"], 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_window_start = max(page_obj.number - 2, 1)
    page_window_end = min(page_obj.number + 2, paginator.num_pages)

    context = build_layout_context(request, RISK_ACTIVE_KEY)
    context.update(
        {
            "page_title": RISK_PAGE_TITLE,
            "search_query": search_query,
            "summary_cards": build_summary_cards(RISK_SUMMARY_CARD_SPECS),
            "cohort_total_students": risk_data["total_students"],
            "watchlist_total_students": risk_data["at_risk_students"],
            "risk_rows": page_obj.object_list,
            "page_obj": page_obj,
            "page_numbers": range(page_window_start, page_window_end + 1),
            "total_students": paginator.count,
            "risk_distribution_rows": risk_data["risk_distribution_rows"],
            "risk_driver_rows": risk_data["risk_driver_rows"],
            "risk_level_rows": risk_data["risk_level_rows"],
            "risk_programme_rows": risk_data["risk_programme_rows"],
            "risk_card_narratives": get_risk_card_narratives(risk_data),
        }
    )
    return context

"""Presentation helpers for the story-first landing dashboard."""

from django.conf import settings
from django.urls import reverse

from ..views import build_layout_context
from .ai_insights import get_overview_card_narratives
from .constants import OVERVIEW_ACTIVE_KEY, OVERVIEW_PAGE_TITLE, OVERVIEW_SUMMARY_CARD_SPECS
from .services import build_overview_scope_pills

OVERVIEW_SHELL_NOTES = {
    "enrolled": "Loading unique students in the visible scope.",
    "registered": "Loading registration volume for the visible scope.",
    "pass_rate": "Loading the latest marked outcome mix.",
    "completion_rate": "Loading the latest completion signal.",
    "on_time_graduation": "Loading on-time completion coverage.",
    "first_year_retention": "Loading first-year progression coverage.",
    "students_satisfaction": "Loading the current student performance proxy.",
    "at_risk": "Loading the active watchlist volume.",
}

OVERVIEW_SHELL_ACTION_CARDS = [
    {
        "kicker": "Risk",
        "title": "Review the active watchlist",
        "copy": "Loading the current intervention priorities for the visible cohort.",
        "action_label": "Open risk register",
        "action_url_name": "dashboard:risk",
        "tone": "danger",
    },
    {
        "kicker": "Insights",
        "title": "Inspect the institutional pressure view",
        "copy": "Loading the clearest concentration signal for the current scope.",
        "action_label": "Open insights",
        "action_url_name": "dashboard:insights",
        "tone": "primary",
    },
    {
        "kicker": "Academic Levels",
        "title": "Check where the academic journey bends",
        "copy": "Loading the academic level that needs the next review.",
        "action_label": "Open academic levels",
        "action_url_name": "dashboard:academic-level",
        "tone": "warning",
    },
    {
        "kicker": "Demographics",
        "title": "Explore who makes up this cohort",
        "copy": "Loading the cohort balance and location story for this slice.",
        "action_label": "Open demographics",
        "action_url_name": "dashboard:demographic",
        "tone": "info",
    },
]


def _overview_ai_narratives_enabled():
    """Return whether the landing page should attempt provider-backed chart narratives."""

    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    openai_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules":
        return False

    google_ready = provider in {"auto", "google"} and bool(getattr(settings, "GOOGLE_API_KEY", ""))
    openai_ready = (
        provider in {"auto", "openai"}
        and bool(getattr(settings, "OPENAI_API_KEY", ""))
        and (provider == "openai" or openai_enabled)
    )
    return google_ready or openai_ready


def build_overview_shell_context(request):
    """Build a lightweight first-paint context for the landing dashboard."""

    context = build_layout_context(request, OVERVIEW_ACTIVE_KEY)
    context.update(
        {
            "page_title": OVERVIEW_PAGE_TITLE,
            "summary_cards": [
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "tone": spec["tone"],
                    "value": "--",
                    "note": OVERVIEW_SHELL_NOTES.get(spec["key"], "Loading the current dashboard signal."),
                }
                for spec in OVERVIEW_SUMMARY_CARD_SPECS
            ],
            "scope_pills": build_overview_scope_pills(request),
            "action_cards": [
                {
                    **card,
                    "action_url": reverse(card["action_url_name"]),
                }
                for card in OVERVIEW_SHELL_ACTION_CARDS
            ],
            "overview_ai_narratives_enabled": _overview_ai_narratives_enabled(),
        }
    )
    return context


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

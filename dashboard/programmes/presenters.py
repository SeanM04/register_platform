"""Presentation helpers for the story-first programmes dashboard."""

from django.conf import settings

from ..views import build_layout_context
from .constants import PROGRAMMES_ACTIVE_KEY, PROGRAMMES_PAGE_TITLE, PROGRAMME_SUMMARY_CARD_SPECS
from .services import build_programme_scope_pills

PROGRAMME_SHELL_NOTES = {
    "programmes": "Loading the visible programme portfolio for the selected scope.",
    "registrations": "Loading the current registration footprint across programmes.",
    "students": "Loading the visible student mix across programmes.",
    "average_pass_rate": "Loading the weighted pass-rate signal for the active scope.",
}


def _programme_ai_narratives_enabled():
    """Return whether this request should fetch the slower provider narrative pass."""

    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        return False

    google_ready = provider in {"auto", "google"} and bool(getattr(settings, "GOOGLE_API_KEY", ""))
    openai_ready = (
        provider in {"auto", "openai"}
        and bool(getattr(settings, "OPENAI_API_KEY", ""))
        and (provider == "openai" or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False))
    )
    return google_ready or openai_ready


def build_programme_shell_context(request, search_query=""):
    """Build a lightweight first-paint context for the programme dashboard page."""

    sort_key = request.GET.get("sort", "").strip()
    sort_direction = request.GET.get("direction", "asc").strip().lower()

    context = build_layout_context(request, PROGRAMMES_ACTIVE_KEY)
    context.update(
        {
            "page_title": PROGRAMMES_PAGE_TITLE,
            "search_query": search_query,
            "sort_key": sort_key,
            "sort_direction": sort_direction,
            "summary_cards": [
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "tone": spec["tone"],
                    "value": "--",
                    "note": PROGRAMME_SHELL_NOTES.get(spec["key"], "Loading current programme context."),
                }
                for spec in PROGRAMME_SUMMARY_CARD_SPECS
            ],
            "scope_pills": build_programme_scope_pills(request, search_query),
            "programme_ai_narratives_enabled": _programme_ai_narratives_enabled(),
        }
    )
    return context

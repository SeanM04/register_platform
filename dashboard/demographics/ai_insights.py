"""Narrative helpers for the demographics dashboard overview cards.

This module mirrors the academic-level AI insight flow:

- always build deterministic rule-based narratives first
- optionally ask Google Gemini or OpenAI to rewrite the overview copy
- validate and normalize provider responses before the page uses them

The demographics page keeps drilldown and interaction-specific copy local in the frontend.
This backend module only owns the overview card narratives for:

- ``gender``
- ``location``
- ``location_mix``
- ``programme``
- ``origin_map``
"""

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache

from django.conf import settings


logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
GOOGLE_GENERATE_CONTENT_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEMOGRAPHIC_CARD_SEVERITIES = {"stable", "medium", "high"}
DEMOGRAPHIC_CARD_CONFIDENCES = {"low", "medium", "high"}
DEMOGRAPHIC_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
DEMOGRAPHIC_CARD_KEYS = ("gender", "location", "location_mix", "programme", "origin_map")
PROVIDER_LABELS = {
    "google": "Google Gemini",
    "openai": "OpenAI",
    "rules": "Rule-based engine",
    "auto": "Automatic provider selection",
}
DEMOGRAPHIC_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": list(DEMOGRAPHIC_CARD_KEYS),
            "properties": {
                card_key: {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["insight", "action"],
                    "properties": {
                        "insight": {"type": "string"},
                        "action": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                }
                for card_key in DEMOGRAPHIC_CARD_KEYS
            },
        }
    },
}


def _parse_percentage(value):
    """Convert percentage display text like ``54%`` into an integer."""

    text = str(value or "").strip().replace("%", "")
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _format_programme_name(value):
    """Shorten verbose programme names so narrative text stays compact."""

    text = str(value or "").strip()
    lowered = text.lower()
    for prefix in ("bachelor of ", "masters of ", "master of "):
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break
    if text.lower().endswith(" honours degree"):
        text = text[:-len(" honours degree")]
    return text.strip() or str(value or "").strip()


def _truncate_text(value, max_length=44):
    """Clamp long narrative labels to a fixed display length."""

    value = str(value or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length - 3].rstrip()}..."


def _get_dominant_gender(counts):
    """Return the leading gender bucket for a location or programme row."""

    ranked_counts = sorted(
        [
            {"label": "Male", "count": int(counts.get("male", 0) or 0)},
            {"label": "Female", "count": int(counts.get("female", 0) or 0)},
            {"label": "Unspecified", "count": int(counts.get("unspecified", 0) or 0)},
        ],
        key=lambda item: (-item["count"], item["label"]),
    )
    return ranked_counts[0] if ranked_counts and ranked_counts[0]["count"] > 0 else None


def build_demographic_fact_pack(demographic_data):
    """Convert demographic aggregates into a compact, provider-safe fact pack."""

    total_students = int(demographic_data.get("total_students", 0) or 0)
    gender_rows = [
        row
        for row in demographic_data.get("gender_rows", [])
        if int(row.get("count", 0) or 0) > 0 and str(row.get("label", "")).strip().lower() != "unspecified"
    ]
    gender_rows.sort(key=lambda row: (-int(row.get("count", 0) or 0), str(row.get("label", ""))))

    location_rows = [
        row
        for row in demographic_data.get("location_rows", [])
        if int(row.get("count", 0) or 0) > 0 and str(row.get("place", "")).strip().lower() != "unspecified"
    ]
    location_rows.sort(key=lambda row: (-int(row.get("count", 0) or 0), str(row.get("place", ""))))

    location_mix_rows = [
        row
        for row in demographic_data.get("location_mix_rows", [])
        if int(row.get("total", 0) or 0) > 0 and str(row.get("place", "")).strip().lower() != "unspecified"
    ]
    location_mix_rows.sort(key=lambda row: (-int(row.get("total", 0) or 0), str(row.get("place", ""))))

    programme_rows = [
        row
        for row in demographic_data.get("programme_rows", [])
        if int(row.get("total", 0) or 0) > 0
    ]
    programme_rows.sort(key=lambda row: (-int(row.get("total", 0) or 0), str(row.get("programme", ""))))

    location_map_rows = [
        row
        for row in demographic_data.get("location_map_rows", [])
        if int(row.get("count", 0) or 0) > 0
    ]
    location_map_rows.sort(key=lambda row: (-int(row.get("count", 0) or 0), str(row.get("place", ""))))
    location_map_meta = demographic_data.get("location_map_meta", {})

    gender_leader = gender_rows[0] if gender_rows else None
    gender_runner_up = gender_rows[1] if len(gender_rows) > 1 else None
    location_leader = location_rows[0] if location_rows else None
    location_runner_up = location_rows[1] if len(location_rows) > 1 else None
    location_mix_leader = location_mix_rows[0] if location_mix_rows else None
    programme_leader = programme_rows[0] if programme_rows else None
    mapped_leader = location_map_rows[0] if location_map_rows else None

    location_mix_facts = []
    for row in location_mix_rows[:8]:
        dominant_gender = _get_dominant_gender(row)
        total = int(row.get("total", 0) or 0)
        location_mix_facts.append(
            {
                "place": row.get("place", ""),
                "students": total,
                "share_pct": _parse_percentage(row.get("share")),
                "dominant_gender": dominant_gender["label"] if dominant_gender else "",
                "dominant_gender_students": dominant_gender["count"] if dominant_gender else 0,
                "dominant_gender_share_pct": round((dominant_gender["count"] / total) * 100) if dominant_gender and total else 0,
                "male": int(row.get("male", 0) or 0),
                "female": int(row.get("female", 0) or 0),
                "unspecified": int(row.get("unspecified", 0) or 0),
            }
        )

    programme_facts = []
    for row in programme_rows[:8]:
        dominant_gender = _get_dominant_gender(row)
        total = int(row.get("total", 0) or 0)
        programme_facts.append(
            {
                "programme": row.get("programme", ""),
                "students": total,
                "dominant_gender": dominant_gender["label"] if dominant_gender else "",
                "dominant_gender_share_pct": round((dominant_gender["count"] / total) * 100) if dominant_gender and total else 0,
            }
        )

    mapped_students = int(location_map_meta.get("mapped_students", 0) or 0)
    unmapped_students = int(location_map_meta.get("unmapped_students", 0) or 0)

    return {
        "students_total": total_students,
        "gender": {
            "segments": [
                {
                    "label": row.get("label", ""),
                    "students": int(row.get("count", 0) or 0),
                    "share_pct": _parse_percentage(row.get("share")),
                }
                for row in gender_rows
            ],
            "leader": gender_leader.get("label", "") if gender_leader else "",
            "leader_share_pct": _parse_percentage(gender_leader.get("share")) if gender_leader else 0,
            "runner_up": gender_runner_up.get("label", "") if gender_runner_up else "",
            "representation_gap_pct": (
                abs(_parse_percentage(gender_leader.get("share")) - _parse_percentage(gender_runner_up.get("share")))
                if gender_leader and gender_runner_up
                else 0
            ),
        },
        "location": {
            "top_locations": [
                {
                    "place": row.get("place", ""),
                    "students": int(row.get("count", 0) or 0),
                    "share_pct": _parse_percentage(row.get("share")),
                }
                for row in location_rows[:8]
            ],
            "leader_place": location_leader.get("place", "") if location_leader else "",
            "leader_share_pct": _parse_percentage(location_leader.get("share")) if location_leader else 0,
            "runner_up_place": location_runner_up.get("place", "") if location_runner_up else "",
            "visible_locations": len(location_rows),
        },
        "location_mix": {
            "locations": location_mix_facts,
            "leader_place": location_mix_leader.get("place", "") if location_mix_leader else "",
            "leader_students": int(location_mix_leader.get("total", 0) or 0) if location_mix_leader else 0,
            "leader_share_pct": _parse_percentage(location_mix_leader.get("share")) if location_mix_leader else 0,
        },
        "programme": {
            "programmes": programme_facts,
            "leader_programme": programme_leader.get("programme", "") if programme_leader else "",
            "leader_students": int(programme_leader.get("total", 0) or 0) if programme_leader else 0,
            "leader_share_pct": round((int(programme_leader.get("total", 0) or 0) / total_students) * 100) if programme_leader and total_students else 0,
            "visible_programmes": len(programme_rows),
        },
        "origin_map": {
            "mapped_places": int(location_map_meta.get("mapped_places", 0) or 0),
            "mapped_students": mapped_students,
            "unmapped_places": int(location_map_meta.get("unmapped_places", 0) or 0),
            "unmapped_students": unmapped_students,
            "mapped_coverage_pct": round((mapped_students / total_students) * 100) if total_students else 0,
            "lead_mapped_place": mapped_leader.get("place", "") if mapped_leader else "",
            "lead_mapped_share_pct": _parse_percentage(mapped_leader.get("share")) if mapped_leader else 0,
            "unmapped_labels": location_map_meta.get("unmapped_labels", [])[:5],
        },
    }


def _resolve_gender_card_severity(facts):
    segments = facts["gender"]["segments"]
    total_students = int(facts.get("students_total", 0) or 0)
    representation_gap = int(facts["gender"].get("representation_gap_pct", 0) or 0)

    if not segments or total_students < 20:
        return "stable"
    if len(segments) == 1:
        return "high" if total_students >= 50 else "medium"
    if representation_gap >= 15 and total_students >= 50:
        return "high"
    if representation_gap >= 8:
        return "medium"
    return "stable"


def _resolve_gender_card_confidence(facts):
    total_students = int(facts.get("students_total", 0) or 0)
    segment_count = len(facts["gender"]["segments"])
    if total_students >= 120 and segment_count >= 2:
        return "high"
    if total_students >= 40 and segment_count >= 1:
        return "medium"
    return "low"


def _resolve_location_card_severity(facts):
    top_locations = facts["location"]["top_locations"]
    total_students = int(facts.get("students_total", 0) or 0)
    leader_share = int(facts["location"].get("leader_share_pct", 0) or 0)

    if not top_locations or total_students < 20:
        return "stable"
    if leader_share >= 30 and total_students >= 80:
        return "high"
    if leader_share >= 18:
        return "medium"
    return "stable"


def _resolve_location_card_confidence(facts):
    total_students = int(facts.get("students_total", 0) or 0)
    visible_locations = int(facts["location"].get("visible_locations", 0) or 0)
    if total_students >= 120 and visible_locations >= 5:
        return "high"
    if total_students >= 40 and visible_locations >= 2:
        return "medium"
    return "low"


def _resolve_location_mix_card_severity(facts):
    location_rows = facts["location_mix"]["locations"]
    if not location_rows:
        return "stable"

    leader = location_rows[0]
    dominant_share = int(leader.get("dominant_gender_share_pct", 0) or 0)
    leader_students = int(leader.get("students", 0) or 0)
    if dominant_share >= 75 and leader_students >= 60:
        return "high"
    if dominant_share >= 62 and leader_students >= 30:
        return "medium"
    return "stable"


def _resolve_location_mix_card_confidence(facts):
    location_rows = facts["location_mix"]["locations"]
    if not location_rows:
        return "low"

    leader_students = int(location_rows[0].get("students", 0) or 0)
    if len(location_rows) >= 4 and leader_students >= 60:
        return "high"
    if len(location_rows) >= 2 and leader_students >= 20:
        return "medium"
    return "low"


def _resolve_programme_card_severity(facts):
    programmes = facts["programme"]["programmes"]
    leader_share = int(facts["programme"].get("leader_share_pct", 0) or 0)
    leader_students = int(facts["programme"].get("leader_students", 0) or 0)

    if not programmes or leader_students < 20:
        return "stable"
    if leader_share >= 28 and leader_students >= 60:
        return "high"
    if leader_share >= 18:
        return "medium"
    return "stable"


def _resolve_programme_card_confidence(facts):
    total_students = int(facts.get("students_total", 0) or 0)
    visible_programmes = int(facts["programme"].get("visible_programmes", 0) or 0)
    if total_students >= 120 and visible_programmes >= 5:
        return "high"
    if total_students >= 40 and visible_programmes >= 2:
        return "medium"
    return "low"


def _resolve_origin_map_card_severity(facts):
    origin_map = facts["origin_map"]
    total_students = int(facts.get("students_total", 0) or 0)
    unmapped_students = int(origin_map.get("unmapped_students", 0) or 0)
    coverage_gap_pct = 100 - int(origin_map.get("mapped_coverage_pct", 0) or 0)

    if total_students < 20 or not origin_map.get("mapped_students"):
        return "stable"
    if coverage_gap_pct >= 25 and unmapped_students >= 20:
        return "high"
    if coverage_gap_pct >= 10 and unmapped_students >= 8:
        return "medium"
    return "stable"


def _resolve_origin_map_card_confidence(facts):
    origin_map = facts["origin_map"]
    mapped_students = int(origin_map.get("mapped_students", 0) or 0)
    mapped_places = int(origin_map.get("mapped_places", 0) or 0)
    mapped_coverage_pct = int(origin_map.get("mapped_coverage_pct", 0) or 0)

    if mapped_students >= 100 and mapped_places >= 5 and mapped_coverage_pct >= 80:
        return "high"
    if mapped_students >= 30 and mapped_places >= 2 and mapped_coverage_pct >= 50:
        return "medium"
    return "low"


def build_rule_based_demographic_narratives(demographic_data):
    """Build deterministic overview narratives and safe severity/confidence baselines."""

    facts = build_demographic_fact_pack(demographic_data)
    gender_segments = facts["gender"]["segments"]
    top_locations = facts["location"]["top_locations"]
    location_mix_rows = facts["location_mix"]["locations"]
    programme_rows = facts["programme"]["programmes"]
    origin_map = facts["origin_map"]

    if gender_segments:
        lead_segment = gender_segments[0]
        runner_up = gender_segments[1] if len(gender_segments) > 1 else None
        if runner_up and facts["gender"]["representation_gap_pct"] <= 5:
            gender_insight = (
                f"{lead_segment['label']} and {runner_up['label']} remain close in the visible cohort, "
                f"with {lead_segment['label']} slightly ahead at {lead_segment['share_pct']}%."
            )
        elif runner_up:
            gender_insight = (
                f"{lead_segment['label']} currently leads the visible cohort at {lead_segment['share_pct']}%, "
                f"{facts['gender']['representation_gap_pct']} points ahead of {runner_up['label']}."
            )
        else:
            gender_insight = (
                f"{lead_segment['label']} accounts for {lead_segment['share_pct']}% of the visible cohort "
                "in the current filter view."
            )
        gender_action = "Action: Use the donut tooltip first to compare exact student counts and shares across the visible gender groups."
    else:
        gender_insight = "No gender balance insight is available for the current filters."
        gender_action = "Action: Adjust the current filters to bring the visible cohort mix back into view."

    if top_locations:
        leader = top_locations[0]
        runner_up = top_locations[1] if len(top_locations) > 1 else None
        if runner_up:
            location_insight = (
                f"{leader['place']} currently leads the visible birth-location mix at {leader['share_pct']}%, "
                f"ahead of {runner_up['place']}."
            )
        else:
            location_insight = (
                f"{leader['place']} is the clearest visible birth-location signal at {leader['share_pct']}% "
                "of the current cohort."
            )
        location_action = (
            f"Action: Click {leader['place']} in the column chart first to inspect that location's internal gender split."
        )
    else:
        location_insight = "No birth-location distribution insight is available for the current filters."
        location_action = "Action: Adjust the current filters to bring the birthplace distribution back into view."

    if location_mix_rows:
        leader = location_mix_rows[0]
        dominant_gender = leader.get("dominant_gender", "")
        dominant_share_pct = int(leader.get("dominant_gender_share_pct", 0) or 0)
        location_mix_insight = (
            f"{leader['place']} remains the strongest visible location cluster, and {dominant_gender.lower()} students "
            f"make up {dominant_share_pct}% of that location's cohort."
        ) if dominant_gender else (
            f"{leader['place']} remains the strongest visible location cluster in the current cohort."
        )
        location_mix_action = (
            f"Action: Hover {leader['place']} and the next darkest cells first to compare where the strongest gender concentration sits."
        )
    else:
        location_mix_insight = "No location-to-gender mix insight is available for the current filters."
        location_mix_action = "Action: Adjust the current filters to bring the heatmap story back into view."

    if programme_rows:
        leader = programme_rows[0]
        programme_name = _truncate_text(_format_programme_name(leader["programme"]), 34)
        dominant_gender = leader.get("dominant_gender", "")
        dominant_share_pct = int(leader.get("dominant_gender_share_pct", 0) or 0)
        if dominant_gender and dominant_share_pct:
            programme_insight = (
                f"{programme_name} carries the largest visible programme cohort, and {dominant_gender.lower()} "
                f"students make up {dominant_share_pct}% of that programme's slice."
            )
        else:
            programme_insight = f"{programme_name} carries the largest visible programme cohort in the current slice."
        programme_action = (
            f"Action: Use the stacked-bar tooltip on {programme_name} first to read the full programme name and exact mix."
        )
    else:
        programme_insight = "No programme demographic insight is available for the current filters."
        programme_action = "Action: Adjust the current filters to bring the programme mix back into view."

    if origin_map.get("mapped_students"):
        if origin_map.get("unmapped_students"):
            origin_map_insight = (
                f"{origin_map['mapped_students']} visible students are currently mapped across "
                f"{origin_map['mapped_places']} places, but {origin_map['unmapped_students']} students still sit off-map."
            )
            origin_map_action = (
                "Action: Use the map for spatial clustering, but treat it as partial coverage until the unmapped birth labels are normalized."
            )
        else:
            origin_map_insight = (
                f"{origin_map['lead_mapped_place']} anchors the mapped origin view, and all visible students are currently represented on the Zimbabwe map."
            )
            origin_map_action = (
                f"Action: Click the {origin_map['lead_mapped_place']} marker first to compare it against the next strongest mapped origin cluster."
            )
    else:
        origin_map_insight = "No mapped origin insight is available for the current filters."
        origin_map_action = "Action: Adjust the current filters or extend the location map dictionary to restore geographic coverage."

    return {
        "source": "rules",
        "cards": {
            "gender": {
                "insight": gender_insight,
                "action": gender_action,
                "severity": _resolve_gender_card_severity(facts),
                "confidence": _resolve_gender_card_confidence(facts),
            },
            "location": {
                "insight": location_insight,
                "action": location_action,
                "severity": _resolve_location_card_severity(facts),
                "confidence": _resolve_location_card_confidence(facts),
            },
            "location_mix": {
                "insight": location_mix_insight,
                "action": location_mix_action,
                "severity": _resolve_location_mix_card_severity(facts),
                "confidence": _resolve_location_mix_card_confidence(facts),
            },
            "programme": {
                "insight": programme_insight,
                "action": programme_action,
                "severity": _resolve_programme_card_severity(facts),
                "confidence": _resolve_programme_card_confidence(facts),
            },
            "origin_map": {
                "insight": origin_map_insight,
                "action": origin_map_action,
                "severity": _resolve_origin_map_card_severity(facts),
                "confidence": _resolve_origin_map_card_confidence(facts),
            },
        },
    }


def _extract_response_text(response_payload):
    """Read the first non-empty text body from an OpenAI Responses API payload."""

    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in response_payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    return ""


def _extract_google_response_text(response_payload):
    """Read the first non-empty text part from a Gemini ``generateContent`` response."""

    for candidate in response_payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if isinstance(part.get("text"), str) and part["text"].strip():
                return part["text"]
    return ""


def _get_provider_label(provider):
    """Return a user-facing label for the configured narrative provider."""

    return PROVIDER_LABELS.get(str(provider or "").strip().lower(), "Unknown provider")


def _trim_diagnostic_detail(value, max_length=180):
    """Clamp verbose provider error text before returning it to the UI."""

    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - 3].rstrip()}..."


def _classify_provider_error(provider_name, error):
    """Normalize provider exceptions into stable diagnostic reason codes."""

    detail = _trim_diagnostic_detail(error)
    lowered_detail = detail.lower()
    provider_key = str(provider_name or "provider").strip().lower()

    if isinstance(error, urllib.error.HTTPError):
        if int(getattr(error, "code", 0) or 0) == 429:
            return (
                f"{provider_key}_rate_limited",
                f"{_get_provider_label(provider_key)} rate-limited the request because quota or request limits were reached.",
                detail,
            )
        return (
            f"{provider_key}_http_error",
            f"{_get_provider_label(provider_key)} returned HTTP {error.code}.",
            detail,
        )
    if isinstance(error, urllib.error.URLError):
        if "10013" in lowered_detail or "forbidden by its access permissions" in lowered_detail:
            return (
                f"{provider_key}_network_blocked",
                f"{_get_provider_label(provider_key)} could not be reached because outbound network access is blocked on this host.",
                detail,
            )
        if "timed out" in lowered_detail or "timeout" in lowered_detail:
            return (
                f"{provider_key}_timeout",
                f"{_get_provider_label(provider_key)} timed out before returning demographics narratives.",
                detail,
            )
        return (
            f"{provider_key}_network_error",
            f"{_get_provider_label(provider_key)} could not be reached from this environment.",
            detail,
        )
    if isinstance(error, json.JSONDecodeError):
        return (
            f"{provider_key}_invalid_json",
            f"{_get_provider_label(provider_key)} returned a response that could not be parsed as JSON.",
            detail,
        )
    if isinstance(error, ValueError):
        return (
            f"{provider_key}_invalid_payload",
            f"{_get_provider_label(provider_key)} returned an incomplete or invalid narrative payload.",
            detail,
        )
    if isinstance(error, OSError):
        return (
            f"{provider_key}_os_error",
            f"{_get_provider_label(provider_key)} could not be reached because of an operating-system network error.",
            detail,
        )
    return (
        f"{provider_key}_unexpected_error",
        f"{_get_provider_label(provider_key)} failed unexpectedly while generating demographics narratives.",
        detail,
    )


def _build_demographic_narrative_diagnostics(
    *,
    configured_provider,
    returned_source,
    status,
    provider_attempted="",
    fallback_reason="",
    message="",
    fallback_detail="",
):
    """Build structured diagnostics for the demographics narrative pipeline."""

    return {
        "configured_provider": str(configured_provider or "rules").strip().lower() or "rules",
        "provider_attempted": str(provider_attempted or "").strip().lower(),
        "returned_source": str(returned_source or "rules").strip().lower() or "rules",
        "status": str(status or "rules").strip().lower() or "rules",
        "fallback_reason": str(fallback_reason or "").strip().lower(),
        "message": str(message or "").strip(),
        "fallback_detail": str(fallback_detail or "").strip(),
        "google_configured": bool(getattr(settings, "GOOGLE_API_KEY", "")),
        "openai_configured": bool(getattr(settings, "OPENAI_API_KEY", "")),
        "ai_enabled": bool(
            getattr(settings, "AI_INSIGHTS_ENABLED", False)
            or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
        ),
    }


def _normalize_ai_narrative_payload(payload, source, fallback_cards=None):
    """Validate and normalize provider output into the demographics card contract."""

    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}
    for card_key in DEMOGRAPHIC_CARD_KEYS:
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")
        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in DEMOGRAPHIC_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in DEMOGRAPHIC_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in DEMOGRAPHIC_CARD_SEVERITIES
            and DEMOGRAPHIC_CARD_SEVERITY_RANK[severity] < DEMOGRAPHIC_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity
        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in DEMOGRAPHIC_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in DEMOGRAPHIC_CARD_CONFIDENCES else "medium"
        normalized_cards[card_key] = {
            "insight": insight,
            "action": action,
            "severity": severity,
            "confidence": confidence,
        }
    return {"source": source, "cards": normalized_cards}


def _build_narrative_prompt(fact_pack_json):
    """Build the provider-neutral prompt used for both Gemini and OpenAI requests."""

    return (
        "You generate concise dashboard narratives for a university demographics analytics page.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "Use exact labels from the facts where helpful.\n"
        "If the facts show no issue, the action should suggest monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


@lru_cache(maxsize=64)
def _request_demographic_openai_narratives(fact_pack_json):
    """Request demographics narratives from OpenAI for a single fact-pack snapshot."""

    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "model": settings.OPENAI_INSIGHTS_MODEL,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 700,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Return only structured dashboard narrative fields that match the schema.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "demographic_card_narratives",
                    "schema": DEMOGRAPHIC_NARRATIVE_SCHEMA,
                    "strict": True,
                },
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.OPENAI_INSIGHTS_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


@lru_cache(maxsize=64)
def _request_demographic_google_narratives(fact_pack_json):
    """Request demographics narratives from Gemini for a single fact-pack snapshot."""

    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": "Return only structured dashboard narrative fields that match the schema.",
                }
            ]
        },
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 700,
            "responseMimeType": "application/json",
            "responseJsonSchema": DEMOGRAPHIC_NARRATIVE_SCHEMA,
        },
    }
    request = urllib.request.Request(
        GOOGLE_GENERATE_CONTENT_URL_TEMPLATE.format(model=settings.GOOGLE_INSIGHTS_MODEL),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": settings.GOOGLE_API_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.GOOGLE_INSIGHTS_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def get_demographic_card_narratives_result(demographic_data):
    """Return overview card narratives plus diagnostics for the demographics dashboard page."""

    fallback = build_rule_based_demographic_narratives(demographic_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        fallback_reason = "provider_rules_configured" if provider == "rules" else "ai_insights_disabled"
        message = (
            "Demographics narratives are using the rule-based engine because AI provider mode is set to rules."
            if provider == "rules"
            else "Demographics narratives are using the rule-based engine because AI insights are disabled."
        )
        return {
            "card_narratives": fallback,
            "diagnostics": _build_demographic_narrative_diagnostics(
                configured_provider=provider,
                returned_source="rules",
                status="rules",
                fallback_reason=fallback_reason,
                message=message,
            ),
        }

    fact_pack_json = json.dumps(build_demographic_fact_pack(demographic_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            raw_response = _request_demographic_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"]),
                "diagnostics": _build_demographic_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="google",
                    returned_source="google",
                    status="ai",
                    message="Demographics narratives were generated by Google Gemini.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after Google demographics narrative request failed: %s", error)
            if provider == "google":
                fallback_reason, message, detail = _classify_provider_error("google", error)
                return {
                    "card_narratives": fallback,
                    "diagnostics": _build_demographic_narrative_diagnostics(
                        configured_provider=provider,
                        provider_attempted="google",
                        returned_source="rules",
                        status="fallback",
                        fallback_reason=fallback_reason,
                        message=message,
                        fallback_detail=detail,
                    ),
                }

    if provider in {"auto", "openai"}:
        if provider == "openai" and not getattr(settings, "OPENAI_API_KEY", ""):
            logger.info("AI_INSIGHTS_PROVIDER is openai but OPENAI_API_KEY is missing; using rule-based demographics narratives.")
            return {
                "card_narratives": fallback,
                "diagnostics": _build_demographic_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Demographics narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }
        if provider == "auto" and not getattr(settings, "OPENAI_INSIGHTS_ENABLED", False):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_demographic_narrative_diagnostics(
                    configured_provider=provider,
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="openai_not_enabled_in_auto_mode",
                    message="Demographics narratives are using the rule-based engine because OpenAI fallback is disabled in auto mode.",
                ),
            }
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_demographic_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai" if provider == "openai" else "",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Demographics narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }

        try:
            raw_response = _request_demographic_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Responses API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"]),
                "diagnostics": _build_demographic_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="openai",
                    status="ai",
                    message="Demographics narratives were generated by OpenAI.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after OpenAI demographics narrative request failed: %s", error)
            fallback_reason, message, detail = _classify_provider_error("openai", error)
            return {
                "card_narratives": fallback,
                "diagnostics": _build_demographic_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason=fallback_reason,
                    message=message,
                    fallback_detail=detail,
                ),
            }

    return {
        "card_narratives": fallback,
        "diagnostics": _build_demographic_narrative_diagnostics(
            configured_provider=provider,
            returned_source="rules",
            status="fallback",
            fallback_reason="no_provider_available",
            message="Demographics narratives are using the rule-based engine because no AI provider is currently available.",
        ),
    }


def get_demographic_card_narratives(demographic_data):
    """Return only overview card narratives for compatibility call sites."""

    return get_demographic_card_narratives_result(demographic_data)["card_narratives"]

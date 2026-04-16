"""Narrative helpers for the academic-level dashboard's AI insight cards.

This module takes the aggregated data built by
``dashboard.academic_levels.services.build_academic_level_data``
and turns it into three short overview narratives:

- ``gender``
- ``top_enrolment``
- ``pass_trend``

The flow is intentionally defensive. We always build a deterministic rule-based fallback,
then optionally ask Google Gemini or OpenAI to rewrite the copy into shorter card text.
If an AI provider is disabled, misconfigured, times out, or returns invalid JSON, the
dashboard still renders with the rule-based version.
"""

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache

from django.conf import settings

from .constants import ACADEMIC_LEVEL_PASS_TARGET


logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
GOOGLE_GENERATE_CONTENT_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ACADEMIC_LEVEL_CARD_SEVERITIES = {"stable", "medium", "high"}
ACADEMIC_LEVEL_CARD_CONFIDENCES = {"low", "medium", "high"}
ACADEMIC_LEVEL_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
PROVIDER_LABELS = {
    "google": "Google Gemini",
    "openai": "OpenAI",
    "rules": "Rule-based engine",
    "auto": "Automatic provider selection",
}
ACADEMIC_LEVEL_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": ["gender", "top_enrolment", "pass_trend"],
            "properties": {
                "gender": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["insight", "action"],
                    "properties": {
                        "insight": {"type": "string"},
                        "action": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                },
                "top_enrolment": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["insight", "action"],
                    "properties": {
                        "insight": {"type": "string"},
                        "action": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                },
                "pass_trend": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["insight", "action"],
                    "properties": {
                        "insight": {"type": "string"},
                        "action": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                },
            },
        },
    },
}


def _format_programme_name(value):
    """Shorten verbose programme names so card copy can stay compact and readable."""

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
    """Clamp narrative text to a fixed display length while preserving an ellipsis."""

    value = str(value or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length - 3].rstrip()}..."


def _find_strongest_and_weakest_level(level_rows):
    """Return the best and weakest visible level rows using pass rate, marks, then label."""

    if not level_rows:
        return None, None
    sorted_rows = sorted(
        level_rows,
        key=lambda row: (
            -int(row.get("pass_rate_value", 0)),
            -int(row.get("average_mark", 0)),
            str(row.get("level", "")),
        ),
    )
    return sorted_rows[0], sorted_rows[-1]


def build_academic_level_fact_pack(academic_level_data):
    """Convert academic-level chart data into a compact fact pack for rules and AI prompts.

    The input is the dictionary returned by
    ``dashboard.academic_levels.services.build_academic_level_data``. The result is
    intentionally JSON-friendly so it can be used both by rule-based narrative builders and
    by external AI providers.
    """

    level_rows = academic_level_data.get("level_chart_rows", [])
    gender_rows = academic_level_data.get("gender_performance_rows", [])
    programme_rows = academic_level_data.get("programme_performance_rows", [])

    strongest_level, weakest_level = _find_strongest_and_weakest_level(level_rows)
    below_target_rows = [
        row for row in level_rows
        if int(row.get("pass_rate_value", 0)) < ACADEMIC_LEVEL_PASS_TARGET
    ]
    visible_gender_rows = [
        row for row in gender_rows
        if int(row.get("students", 0)) > 0 and row.get("key") != "unspecified"
    ]
    visible_gender_rows.sort(
        key=lambda row: (-int(row.get("student_share_value", 0)), str(row.get("label", "")))
    )
    top_programme_rows = sorted(
        programme_rows,
        key=lambda row: (-int(row.get("registrations", 0)), str(row.get("programme", ""))),
    )[:5]
    top_programme_total = sum(int(row.get("registrations", 0)) for row in top_programme_rows)
    top_programme_leader = top_programme_rows[0] if top_programme_rows else None

    return {
        "pass_target": ACADEMIC_LEVEL_PASS_TARGET,
        "gender": {
            "segments": [
                {
                    "label": row.get("label", ""),
                    "students": int(row.get("students", 0)),
                    "share_pct": int(row.get("student_share_value", 0)),
                    "pass_rate_pct": int(row.get("pass_rate_value", 0)),
                    "average_mark": row.get("average_mark_display", "--"),
                }
                for row in visible_gender_rows
            ],
            "leader": visible_gender_rows[0]["label"] if visible_gender_rows else "",
            "leader_share_pct": int(visible_gender_rows[0]["student_share_value"]) if visible_gender_rows else 0,
            "representation_gap_pct": (
                abs(
                    int(visible_gender_rows[0]["student_share_value"])
                    - int(visible_gender_rows[1]["student_share_value"])
                )
                if len(visible_gender_rows) > 1
                else 0
            ),
        },
        "top_enrolment": {
            "top_programmes": [
                {
                    "programme": row.get("programme", ""),
                    "registrations": int(row.get("registrations", 0)),
                    "students": int(row.get("students", 0)),
                    "pass_rate_pct": int(row.get("pass_rate_value", 0)),
                    "average_mark": int(row.get("average_mark", 0)),
                }
                for row in top_programme_rows
            ],
            "total_top_five_registrations": top_programme_total,
            "leader_programme": top_programme_leader.get("programme", "") if top_programme_leader else "",
            "leader_share_pct": (
                round((int(top_programme_leader.get("registrations", 0)) / top_programme_total) * 100)
                if top_programme_leader and top_programme_total
                else 0
            ),
        },
        "pass_trend": {
            "levels": [
                {
                    "level": row.get("level", ""),
                    "pass_rate_pct": int(row.get("pass_rate_value", 0)),
                    "average_mark": int(row.get("average_mark", 0)),
                    "registrations": int(row.get("registrations", 0)),
                    "top_programme": row.get("top_programme", ""),
                }
                for row in level_rows
            ],
            "total_registrations": sum(int(row.get("registrations", 0)) for row in level_rows),
            "strongest_level": strongest_level.get("level", "") if strongest_level else "",
            "strongest_pass_rate_pct": int(strongest_level.get("pass_rate_value", 0)) if strongest_level else 0,
            "weakest_level": weakest_level.get("level", "") if weakest_level else "",
            "weakest_pass_rate_pct": int(weakest_level.get("pass_rate_value", 0)) if weakest_level else 0,
            "below_target_count": len(below_target_rows),
            "below_target_levels": [row.get("level", "") for row in below_target_rows],
        },
    }


def _resolve_gender_card_severity(facts):
    """Estimate how urgent the gender-balance card should feel for the current cohort."""

    segments = facts["gender"]["segments"]
    total_students = sum(int(segment.get("students", 0)) for segment in segments)
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


def _resolve_top_enrolment_card_severity(facts):
    """Estimate how concentrated the visible top-programme load appears to be."""

    top_enrolment = facts["top_enrolment"]
    top_programmes = top_enrolment["top_programmes"]
    total_registrations = int(top_enrolment.get("total_top_five_registrations", 0) or 0)
    leader_share = int(top_enrolment.get("leader_share_pct", 0) or 0)

    if len(top_programmes) < 2 or total_registrations < 80:
        return "stable"
    if leader_share >= 35 and total_registrations >= 200:
        return "high"
    if leader_share >= 25:
        return "medium"
    return "stable"


def _resolve_pass_trend_card_severity(facts):
    """Estimate how much attention the pass-trend card should demand."""

    pass_trend = facts["pass_trend"]
    if not pass_trend["levels"]:
        return "stable"

    below_target_count = int(pass_trend.get("below_target_count", 0) or 0)
    weakest_pass_rate = int(pass_trend.get("weakest_pass_rate_pct", 0) or 0)
    strongest_pass_rate = int(pass_trend.get("strongest_pass_rate_pct", 0) or 0)
    pass_spread = max(strongest_pass_rate - weakest_pass_rate, 0)

    if below_target_count:
        return "high"
    if pass_spread >= 6 or weakest_pass_rate <= 88:
        return "medium"
    return "stable"


def _resolve_gender_card_confidence(facts):
    """Score confidence for the gender card based on visible cohort size and coverage."""

    segments = facts["gender"]["segments"]
    total_students = sum(int(segment.get("students", 0)) for segment in segments)

    if len(segments) >= 2 and total_students >= 120:
        return "high"
    if total_students >= 30:
        return "medium"
    return "low"


def _resolve_top_enrolment_card_confidence(facts):
    """Score confidence for the programme-load card from data volume and breadth."""

    top_enrolment = facts["top_enrolment"]
    top_programmes = top_enrolment["top_programmes"]
    total_registrations = int(top_enrolment.get("total_top_five_registrations", 0) or 0)

    if len(top_programmes) >= 4 and total_registrations >= 250:
        return "high"
    if len(top_programmes) >= 2 and total_registrations >= 80:
        return "medium"
    return "low"


def _resolve_pass_trend_card_confidence(facts):
    """Score confidence for the pass-trend card from level coverage and registration volume."""

    pass_trend = facts["pass_trend"]
    level_count = len(pass_trend["levels"])
    total_registrations = int(pass_trend.get("total_registrations", 0) or 0)

    if level_count >= 4 and total_registrations >= 150:
        return "high"
    if level_count >= 2 and total_registrations >= 40:
        return "medium"
    return "low"


def build_rule_based_academic_level_narratives(academic_level_data):
    """Build deterministic card narratives and baseline severity/confidence values.

    These narratives are always available and serve two roles:

    - they are the final output when AI insights are disabled or fail
    - they provide safe fallback severity/confidence values when AI text is accepted
    """

    facts = build_academic_level_fact_pack(academic_level_data)
    gender_segments = facts["gender"]["segments"]
    top_programmes = facts["top_enrolment"]["top_programmes"]
    pass_trend = facts["pass_trend"]

    if gender_segments:
        lead_segment = gender_segments[0]
        runner_up = gender_segments[1] if len(gender_segments) > 1 else None
        if runner_up and facts["gender"]["representation_gap_pct"] <= 5:
            gender_insight = (
                f"{lead_segment['label']} and {runner_up['label']} representation is close to balanced, "
                f"with {lead_segment['label']} slightly ahead at {lead_segment['share_pct']}%."
            )
        elif runner_up:
            gender_insight = (
                f"{lead_segment['label']} currently leads the cohort at {lead_segment['share_pct']}%, "
                f"{facts['gender']['representation_gap_pct']} points ahead of {runner_up['label']}."
            )
        else:
            gender_insight = (
                f"{lead_segment['label']} accounts for {lead_segment['share_pct']}% of the visible cohort "
                "in the current filter view."
            )
        gender_action = (
            "Action: Use the tooltip to confirm whether pass rate and average mark stay aligned "
            "across the visible gender groups."
        )
    else:
        gender_insight = "No gender balance insight is available for the current filters."
        gender_action = "Action: Adjust the current filters to bring the cohort balance story back into view."

    if top_programmes:
        lead_programme = top_programmes[0]
        programme_name = _truncate_text(_format_programme_name(lead_programme["programme"]), 34)
        leader_share = facts["top_enrolment"]["leader_share_pct"]
        if leader_share >= 25:
            top_enrolment_insight = (
                f"{programme_name} carries {leader_share}% of the top-five enrolment load, "
                "so the current intake is concentrated in a small number of programmes."
            )
        else:
            top_enrolment_insight = (
                f"{programme_name} leads the top-five view, but enrolment is still relatively "
                "spread across the biggest programmes."
            )
        top_enrolment_action = (
            f"Action: Click {programme_name} first to see which academic levels are carrying "
            "most of that programme's current load."
        )
    else:
        top_enrolment_insight = "No top-enrolment insight is available for the current filters."
        top_enrolment_action = "Action: Adjust the current filters to bring the programme-load story back into view."

    weakest_level = pass_trend["weakest_level"]
    strongest_level = pass_trend["strongest_level"]
    if pass_trend["levels"]:
        if pass_trend["below_target_count"]:
            pass_trend_insight = (
                f"{weakest_level} is the clearest pass-rate pressure point at "
                f"{pass_trend['weakest_pass_rate_pct']}%, and {pass_trend['below_target_count']} "
                f"level{'s' if pass_trend['below_target_count'] != 1 else ''} still sit below the "
                f"{ACADEMIC_LEVEL_PASS_TARGET}% target."
            )
            pass_trend_action = (
                f"Action: Click {weakest_level} first to see which programmes are holding that level "
                "below target."
            )
        else:
            pass_trend_insight = (
                f"All visible levels are above the {ACADEMIC_LEVEL_PASS_TARGET}% target, with "
                f"{strongest_level} currently leading the pass trend at "
                f"{pass_trend['strongest_pass_rate_pct']}%."
            )
            pass_trend_action = (
                f"Action: Click {weakest_level} first if you want to inspect the softest point "
                "in an otherwise healthy pass trend."
            )
    else:
        pass_trend_insight = "No pass-trend insight is available for the current filters."
        pass_trend_action = "Action: Adjust the current filters to bring the academic-level pass story back into view."

    return {
        "source": "rules",
        "cards": {
            "gender": {
                "insight": gender_insight,
                "action": gender_action,
                "severity": _resolve_gender_card_severity(facts),
                "confidence": _resolve_gender_card_confidence(facts),
            },
            "top_enrolment": {
                "insight": top_enrolment_insight,
                "action": top_enrolment_action,
                "severity": _resolve_top_enrolment_card_severity(facts),
                "confidence": _resolve_top_enrolment_card_confidence(facts),
            },
            "pass_trend": {
                "insight": pass_trend_insight,
                "action": pass_trend_action,
                "severity": _resolve_pass_trend_card_severity(facts),
                "confidence": _resolve_pass_trend_card_confidence(facts),
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


def _normalize_ai_narrative_payload(payload, source, fallback_cards=None):
    """Validate and normalize provider output into the dashboard card contract.

    Missing or invalid severity/confidence fields fall back to the rule-based values. AI is
    also prevented from lowering severity below the deterministic baseline.
    """

    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}
    for card_key in ("gender", "top_enrolment", "pass_trend"):
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")
        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in ACADEMIC_LEVEL_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in ACADEMIC_LEVEL_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in ACADEMIC_LEVEL_CARD_SEVERITIES
            and ACADEMIC_LEVEL_CARD_SEVERITY_RANK[severity] < ACADEMIC_LEVEL_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity
        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in ACADEMIC_LEVEL_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in ACADEMIC_LEVEL_CARD_CONFIDENCES else "medium"
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
        "You generate concise dashboard narratives for a university academic-level analytics page.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "Use exact labels from the facts where helpful.\n"
        "If the facts show no issue, the action should suggest monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


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
                f"{_get_provider_label(provider_key)} timed out before returning academic-level narratives.",
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
        f"{_get_provider_label(provider_key)} failed unexpectedly while generating academic-level narratives.",
        detail,
    )


def _build_academic_level_narrative_diagnostics(
    *,
    configured_provider,
    returned_source,
    status,
    provider_attempted="",
    fallback_reason="",
    message="",
    fallback_detail="",
):
    """Build structured diagnostics for the academic-level narrative pipeline."""

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


@lru_cache(maxsize=64)
def _request_academic_level_openai_narratives(fact_pack_json):
    """Request academic-level narratives from OpenAI for a single fact-pack snapshot.

    The ``lru_cache`` keeps identical fact-pack requests from re-hitting the provider within
    the same Django process.
    """

    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "model": settings.OPENAI_INSIGHTS_MODEL,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 400,
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
                    "name": "academic_level_card_narratives",
                    "schema": ACADEMIC_LEVEL_NARRATIVE_SCHEMA,
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
def _request_academic_level_google_narratives(fact_pack_json):
    """Request academic-level narratives from Gemini for a single fact-pack snapshot.

    The ``lru_cache`` keeps identical fact-pack requests from re-hitting the provider within
    the same Django process.
    """

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
            "maxOutputTokens": 400,
            "responseMimeType": "application/json",
            "responseJsonSchema": ACADEMIC_LEVEL_NARRATIVE_SCHEMA,
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


def get_academic_level_card_narratives_result(academic_level_data):
    """Return the academic-level overview card narratives for the dashboard page.

    Provider selection is controlled through Django settings. Regardless of provider choice,
    this function always returns a valid rule-based payload when AI generation is disabled,
    misconfigured, unavailable, or invalid.
    """

    fallback = build_rule_based_academic_level_narratives(academic_level_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        fallback_reason = "provider_rules_configured" if provider == "rules" else "ai_insights_disabled"
        message = (
            "Academic-level narratives are using the rule-based engine because AI provider mode is set to rules."
            if provider == "rules"
            else "Academic-level narratives are using the rule-based engine because AI insights are disabled."
        )
        return {
            "card_narratives": fallback,
            "diagnostics": _build_academic_level_narrative_diagnostics(
                configured_provider=provider,
                returned_source="rules",
                status="rules",
                fallback_reason=fallback_reason,
                message=message,
            ),
        }

    fact_pack_json = json.dumps(build_academic_level_fact_pack(academic_level_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            raw_response = _request_academic_level_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"]),
                "diagnostics": _build_academic_level_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="google",
                    returned_source="google",
                    status="ai",
                    message="Academic-level narratives were generated by Google Gemini.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after Google narrative request failed: %s", error)
            if provider == "google":
                fallback_reason, message, detail = _classify_provider_error("google", error)
                return {
                    "card_narratives": fallback,
                    "diagnostics": _build_academic_level_narrative_diagnostics(
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
            logger.info("AI_INSIGHTS_PROVIDER is openai but OPENAI_API_KEY is missing; using rule-based narratives.")
            return {
                "card_narratives": fallback,
                "diagnostics": _build_academic_level_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Academic-level narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }
        if provider == "auto" and not getattr(settings, "OPENAI_INSIGHTS_ENABLED", False):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_academic_level_narrative_diagnostics(
                    configured_provider=provider,
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="openai_not_enabled_in_auto_mode",
                    message="Academic-level narratives are using the rule-based engine because OpenAI fallback is disabled in auto mode.",
                ),
            }
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_academic_level_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai" if provider == "openai" else "",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Academic-level narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }

        try:
            raw_response = _request_academic_level_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Responses API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"]),
                "diagnostics": _build_academic_level_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="openai",
                    status="ai",
                    message="Academic-level narratives were generated by OpenAI.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after OpenAI narrative request failed: %s", error)
            fallback_reason, message, detail = _classify_provider_error("openai", error)
            return {
                "card_narratives": fallback,
                "diagnostics": _build_academic_level_narrative_diagnostics(
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
        "diagnostics": _build_academic_level_narrative_diagnostics(
            configured_provider=provider,
            returned_source="rules",
            status="fallback",
            fallback_reason="no_provider_available",
            message="Academic-level narratives are using the rule-based engine because no AI provider is currently available.",
        ),
    }


def get_academic_level_card_narratives(academic_level_data):
    """Return only the academic-level overview card narratives for compatibility call sites."""

    return get_academic_level_card_narratives_result(academic_level_data)["card_narratives"]

"""Narrative helpers for the story-first programmes dashboard.

This mirrors the safe AI narrative pattern used on the other upgraded dashboard tabs:

- deterministic rules are always built first
- Gemini or OpenAI can optionally rewrite the chart-card narratives
- provider responses are validated and normalized before the page uses them
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
PROGRAMME_CARD_SEVERITIES = {"stable", "medium", "high"}
PROGRAMME_CARD_CONFIDENCES = {"low", "medium", "high"}
PROGRAMME_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
PROGRAMME_CARD_KEYS = ("load", "departments", "quality", "performance")
PROGRAMME_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": list(PROGRAMME_CARD_KEYS),
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
                for card_key in PROGRAMME_CARD_KEYS
            },
        }
    },
}

PROVIDER_LABELS = {
    "google": "Google Gemini",
    "openai": "OpenAI",
    "rules": "Rule-based engine",
    "auto": "Automatic provider selection",
}


def _format_count(value):
    """Format counts with grouping so narrative copy stays readable."""

    return f"{int(value or 0):,}"


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
                f"{_get_provider_label(provider_key)} timed out before returning programme narratives.",
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
        f"{_get_provider_label(provider_key)} failed unexpectedly while generating programme narratives.",
        detail,
    )


def _build_programme_narrative_diagnostics(
    *,
    configured_provider,
    returned_source,
    status,
    provider_attempted="",
    fallback_reason="",
    message="",
    fallback_detail="",
):
    """Build structured diagnostics for the programme narrative pipeline.

    The diagnostics payload is included alongside the programme card narratives and is
    consumed by the frontend for debugging, feature flags, and AI source checks.

    Fields:
    - configured_provider: current AI provider mode from settings (`rules`, `auto`, `google`, `openai`)
    - provider_attempted: the provider actually called if AI was enabled
    - returned_source: the source of the final narrative payload (`google`, `openai`, `rules`)
    - status: whether the final payload is `ai`, `fallback`, or `rules`
    - fallback_reason: a stable code for why the rule-based fallback was used
    - message: a user-friendly summary of what happened for the current page render
    - fallback_detail: optional verbose provider error details for local debugging
    - google_configured / openai_configured / ai_enabled: runtime feature detection values
    """

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


def build_programme_fact_pack(programme_data):
    """Convert programme aggregates into a compact fact pack for AI prompts."""

    load_rows = [
        {
            "name": row.get("name", ""),
            "faculty": row.get("faculty", ""),
            "department": row.get("department", ""),
            "registrations": int(row.get("registrations", 0) or 0),
            "students": int(row.get("students", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
            "pass_rate_pct": int(row.get("pass_rate_value", 0) or 0),
        }
        for row in programme_data.get("top_load_rows", [])
        if int(row.get("registrations", 0) or 0) > 0
    ]
    department_rows = [
        {
            "department": row.get("department", ""),
            "faculty": row.get("faculty", ""),
            "registrations": int(row.get("registrations", 0) or 0),
            "programme_count": int(row.get("programme_count", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
            "pass_rate_pct": int(row.get("pass_rate_value", 0) or 0),
        }
        for row in programme_data.get("department_rows", [])
        if int(row.get("registrations", 0) or 0) > 0
    ]
    quality_rows = [
        {
            "name": row.get("name", ""),
            "faculty": row.get("faculty", ""),
            "pass_rate_pct": int(row.get("pass_rate_value", 0) or 0),
            "registrations": int(row.get("registrations", 0) or 0),
            "marked_results": int(row.get("marked_results", 0) or 0),
        }
        for row in programme_data.get("low_pass_rows", [])
        if int(row.get("marked_results", 0) or 0) > 0
    ]
    performance_rows = [
        {
            "name": row.get("name", ""),
            "registrations": int(row.get("registrations", 0) or 0),
            "students": int(row.get("students", 0) or 0),
            "pass_rate_pct": int(row.get("pass_rate_value", 0) or 0),
            "average_mark": int(round(float(row.get("average_mark_value", 0) or 0))),
        }
        for row in programme_data.get("performance_rows", [])
        if int(row.get("registrations", 0) or 0) > 0
    ]
    programme_rows = [
        {
            "name": row.get("name", ""),
            "registrations": int(row.get("registrations", 0) or 0),
            "marked_results": int(row.get("marked_results", 0) or 0),
            "pass_count": int(row.get("pass_count", 0) or 0),
            "pass_rate_pct": int(row.get("pass_rate_value", 0) or 0),
        }
        for row in programme_data.get("programme_rows", [])
    ]

    total_programmes = len(programme_rows)
    total_registrations = sum(row["registrations"] for row in programme_rows)
    total_students = sum(int(row.get("students", 0) or 0) for row in programme_data.get("programme_rows", []))
    total_marked_results = sum(row["marked_results"] for row in programme_rows)
    total_pass_results = sum(row["pass_count"] for row in programme_rows)
    weighted_pass_rate_pct = round((total_pass_results / total_marked_results) * 100) if total_marked_results else 0
    under_sixty_total = sum(1 for row in programme_rows if row["marked_results"] and row["pass_rate_pct"] < 60)
    under_seventy_total = sum(1 for row in programme_rows if row["marked_results"] and row["pass_rate_pct"] < 70)

    load_rows.sort(key=lambda row: (-row["registrations"], row["name"]))
    department_rows.sort(key=lambda row: (-row["registrations"], row["department"]))
    quality_rows.sort(key=lambda row: (row["pass_rate_pct"], -row["registrations"], row["name"]))
    performance_rows.sort(key=lambda row: (-row["registrations"], row["pass_rate_pct"], row["name"]))

    lead_load = load_rows[0] if load_rows else None
    runner_up_load = load_rows[1] if len(load_rows) > 1 else None
    lead_department = department_rows[0] if department_rows else None
    runner_up_department = department_rows[1] if len(department_rows) > 1 else None
    weakest_programme = quality_rows[0] if quality_rows else None
    biggest_programme = performance_rows[0] if performance_rows else None
    weak_high_load = next(
        (row for row in performance_rows if row["registrations"] >= 50 and row["pass_rate_pct"] < 60),
        None,
    )

    return {
        "total_programmes": total_programmes,
        "total_registrations": total_registrations,
        "total_students": total_students,
        "weighted_pass_rate_pct": weighted_pass_rate_pct,
        "load": {
            "rows": load_rows,
            "leader": lead_load["name"] if lead_load else "",
            "leader_share_pct": int((lead_load or {}).get("share_pct", 0) or 0),
            "leader_registrations": int((lead_load or {}).get("registrations", 0) or 0),
            "runner_up": runner_up_load["name"] if runner_up_load else "",
            "runner_up_share_pct": int((runner_up_load or {}).get("share_pct", 0) or 0),
            "share_gap_pct": (
                int((lead_load or {}).get("share_pct", 0) or 0) - int((runner_up_load or {}).get("share_pct", 0) or 0)
                if lead_load and runner_up_load
                else 0
            ),
        },
        "departments": {
            "rows": department_rows,
            "leader": lead_department["department"] if lead_department else "",
            "leader_share_pct": int((lead_department or {}).get("share_pct", 0) or 0),
            "leader_registrations": int((lead_department or {}).get("registrations", 0) or 0),
            "leader_programmes": int((lead_department or {}).get("programme_count", 0) or 0),
            "runner_up": runner_up_department["department"] if runner_up_department else "",
            "share_gap_pct": (
                int((lead_department or {}).get("share_pct", 0) or 0) - int((runner_up_department or {}).get("share_pct", 0) or 0)
                if lead_department and runner_up_department
                else 0
            ),
        },
        "quality": {
            "rows": quality_rows,
            "weakest_programme": weakest_programme["name"] if weakest_programme else "",
            "weakest_pass_rate_pct": int((weakest_programme or {}).get("pass_rate_pct", 0) or 0),
            "under_sixty_total": under_sixty_total,
            "under_seventy_total": under_seventy_total,
        },
        "performance": {
            "rows": performance_rows,
            "biggest_programme": biggest_programme["name"] if biggest_programme else "",
            "biggest_registrations": int((biggest_programme or {}).get("registrations", 0) or 0),
            "biggest_pass_rate_pct": int((biggest_programme or {}).get("pass_rate_pct", 0) or 0),
            "weak_high_load_programme": weak_high_load["name"] if weak_high_load else "",
            "weak_high_load_registrations": int((weak_high_load or {}).get("registrations", 0) or 0),
            "weak_high_load_pass_rate_pct": int((weak_high_load or {}).get("pass_rate_pct", 0) or 0),
        },
    }


def _resolve_load_severity(facts):
    if int(facts.get("total_registrations", 0) or 0) == 0:
        return "stable"
    load = facts["load"]
    if load["leader_share_pct"] >= 30 or load["share_gap_pct"] >= 12:
        return "high"
    if load["leader_share_pct"] >= 20 or load["share_gap_pct"] >= 6:
        return "medium"
    return "stable"


def _resolve_load_confidence(facts):
    total_programmes = int(facts.get("total_programmes", 0) or 0)
    total_registrations = int(facts.get("total_registrations", 0) or 0)
    if total_programmes >= 5 and total_registrations >= 250:
        return "high"
    if total_programmes >= 2 and total_registrations >= 60:
        return "medium"
    return "low"


def _resolve_department_severity(facts):
    departments = facts["departments"]
    if not departments["rows"]:
        return "stable"
    if departments["leader_share_pct"] >= 45 or departments["share_gap_pct"] >= 15:
        return "high"
    if departments["leader_share_pct"] >= 30 or departments["leader_programmes"] >= 3:
        return "medium"
    return "stable"


def _resolve_department_confidence(facts):
    row_count = len(facts["departments"]["rows"])
    total_registrations = int(facts.get("total_registrations", 0) or 0)
    if row_count >= 3 and total_registrations >= 180:
        return "high"
    if row_count >= 2 and total_registrations >= 50:
        return "medium"
    return "low"


def _resolve_quality_severity(facts):
    quality = facts["quality"]
    if not quality["rows"]:
        return "stable"
    if quality["weakest_pass_rate_pct"] < 50 or quality["under_sixty_total"] >= 3:
        return "high"
    if quality["weakest_pass_rate_pct"] < 65 or quality["under_seventy_total"] >= 2:
        return "medium"
    return "stable"


def _resolve_quality_confidence(facts):
    quality_count = len(facts["quality"]["rows"])
    total_programmes = int(facts.get("total_programmes", 0) or 0)
    if quality_count >= 4 and total_programmes >= 6:
        return "high"
    if quality_count >= 1 and total_programmes >= 2:
        return "medium"
    return "low"


def _resolve_performance_severity(facts):
    performance = facts["performance"]
    if not performance["rows"]:
        return "stable"
    if performance["weak_high_load_programme"]:
        return "high"
    if performance["biggest_pass_rate_pct"] < 70:
        return "medium"
    return "stable"


def _resolve_performance_confidence(facts):
    row_count = len(facts["performance"]["rows"])
    total_registrations = int(facts.get("total_registrations", 0) or 0)
    if row_count >= 5 and total_registrations >= 180:
        return "high"
    if row_count >= 2 and total_registrations >= 60:
        return "medium"
    return "low"


def build_rule_based_programme_narratives(programme_data):
    """Build deterministic programme card narratives and safe severity baselines."""

    facts = build_programme_fact_pack(programme_data)
    load = facts["load"]
    departments = facts["departments"]
    quality = facts["quality"]
    performance = facts["performance"]

    if load["rows"]:
        load_insight = (
            f"{load['leader']} currently carries {load['leader_share_pct']}% of visible registrations"
            + (f", ahead of {load['runner_up']}" if load['runner_up'] else "")
            + "."
        )
        load_action = "Use the load chart first to separate flagship volume from the wider programme portfolio before opening the register."
    else:
        load_insight = "No programme-load story is available for the current filters."
        load_action = "Adjust the current filters to bring the visible programme mix back into view."

    if departments["rows"]:
        departments_insight = (
            f"{departments['leader']} currently anchors {departments['leader_share_pct']}% of visible programme registrations across "
            f"{departments['leader_programmes']} programmes."
        )
        departments_action = "Use the department chart to see whether pressure is isolated to one portfolio or spread across multiple teams."
    else:
        departments_insight = "No department concentration story is available for the current filters."
        departments_action = "Adjust the current filters to bring department-level programme concentration back into view."

    if quality["rows"]:
        quality_insight = (
            f"{quality['weakest_programme']} currently has the lowest visible pass rate at {quality['weakest_pass_rate_pct']}%, "
            f"with {_format_count(quality['under_sixty_total'])} programmes below 60%."
        )
        quality_action = "Use the quality ranking to decide which programmes should move from monitoring into academic review first."
    else:
        quality_insight = "No pass-rate quality story is available for the current filters."
        quality_action = "Adjust the current filters to bring marked programme performance back into view."

    if performance["rows"]:
        if performance["weak_high_load_programme"]:
            performance_insight = (
                f"{performance['weak_high_load_programme']} combines {_format_count(performance['weak_high_load_registrations'])} registrations "
                f"with a {performance['weak_high_load_pass_rate_pct']}% pass rate."
            )
        else:
            performance_insight = (
                f"{performance['biggest_programme']} is the largest visible programme at {_format_count(performance['biggest_registrations'])} registrations "
                f"and is currently passing at {performance['biggest_pass_rate_pct']}%."
            )
        performance_action = "Use the performance map to balance scale against quality before committing support or curriculum review time."
    else:
        performance_insight = "No performance-map story is available for the current filters."
        performance_action = "Adjust the current filters to bring registrations-versus-pass-rate patterns back into view."

    return {
        "source": "rules",
        "cards": {
            "load": {
                "insight": load_insight,
                "action": load_action,
                "severity": _resolve_load_severity(facts),
                "confidence": _resolve_load_confidence(facts),
            },
            "departments": {
                "insight": departments_insight,
                "action": departments_action,
                "severity": _resolve_department_severity(facts),
                "confidence": _resolve_department_confidence(facts),
            },
            "quality": {
                "insight": quality_insight,
                "action": quality_action,
                "severity": _resolve_quality_severity(facts),
                "confidence": _resolve_quality_confidence(facts),
            },
            "performance": {
                "insight": performance_insight,
                "action": performance_action,
                "severity": _resolve_performance_severity(facts),
                "confidence": _resolve_performance_confidence(facts),
            },
        },
    }


def _normalize_ai_narrative_payload(payload, source, fallback_cards=None):
    """Validate and normalize provider output into the programme card contract."""

    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}
    for card_key in PROGRAMME_CARD_KEYS:
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")
        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in PROGRAMME_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in PROGRAMME_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in PROGRAMME_CARD_SEVERITIES
            and PROGRAMME_CARD_SEVERITY_RANK[severity] < PROGRAMME_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity
        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in PROGRAMME_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in PROGRAMME_CARD_CONFIDENCES else "medium"
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
        "You generate concise dashboard narratives for a university programme analytics dashboard.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "Use exact labels from the facts where helpful.\n"
        "If the facts show no issue, the action should suggest monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


@lru_cache(maxsize=64)
def _request_programme_openai_narratives(fact_pack_json):
    """Request programme narratives from OpenAI for a single fact-pack snapshot."""

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
                    "name": "programme_card_narratives",
                    "schema": PROGRAMME_NARRATIVE_SCHEMA,
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
def _request_programme_google_narratives(fact_pack_json):
    """Request programme narratives from Gemini for a single fact-pack snapshot."""

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
            "responseJsonSchema": PROGRAMME_NARRATIVE_SCHEMA,
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


def get_programme_card_narratives_result(programme_data):
    """Return programme narratives plus diagnostics for the four chart cards."""

    fallback = build_rule_based_programme_narratives(programme_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        fallback_reason = "provider_rules_configured" if provider == "rules" else "ai_insights_disabled"
        message = (
            "Programme narratives are using the rule-based engine because AI provider mode is set to rules."
            if provider == "rules"
            else "Programme narratives are using the rule-based engine because AI insights are disabled."
        )
        return {
            "card_narratives": fallback,
            "diagnostics": _build_programme_narrative_diagnostics(
                configured_provider=provider,
                returned_source="rules",
                status="rules",
                fallback_reason=fallback_reason,
                message=message,
            ),
        }

    fact_pack_json = json.dumps(build_programme_fact_pack(programme_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            raw_response = _request_programme_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"]),
                "diagnostics": _build_programme_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="google",
                    returned_source="google",
                    status="ai",
                    message="Programme narratives were generated by Google Gemini.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after Google programme narrative request failed: %s", error)
            if provider == "google":
                fallback_reason, message, detail = _classify_provider_error("google", error)
                return {
                    "card_narratives": fallback,
                    "diagnostics": _build_programme_narrative_diagnostics(
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
            logger.info("AI_INSIGHTS_PROVIDER is openai but OPENAI_API_KEY is missing; using rule-based programme narratives.")
            return {
                "card_narratives": fallback,
                "diagnostics": _build_programme_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Programme narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }
        if provider == "auto" and not getattr(settings, "OPENAI_INSIGHTS_ENABLED", False):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_programme_narrative_diagnostics(
                    configured_provider=provider,
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="openai_not_enabled_in_auto_mode",
                    message="Programme narratives are using the rule-based engine because OpenAI fallback is disabled in auto mode.",
                ),
            }
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_programme_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai" if provider == "openai" else "",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Programme narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }

        try:
            raw_response = _request_programme_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Responses API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"]),
                "diagnostics": _build_programme_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="openai",
                    status="ai",
                    message="Programme narratives were generated by OpenAI.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after OpenAI programme narrative request failed: %s", error)
            fallback_reason, message, detail = _classify_provider_error("openai", error)
            return {
                "card_narratives": fallback,
                "diagnostics": _build_programme_narrative_diagnostics(
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
        "diagnostics": _build_programme_narrative_diagnostics(
            configured_provider=provider,
            returned_source="rules",
            status="fallback",
            fallback_reason="no_provider_available",
            message="Programme narratives are using the rule-based engine because no AI provider is currently available.",
        ),
    }


def get_programme_card_narratives(programme_data):
    """Return only the programme card narratives for compatibility call sites."""

    return get_programme_card_narratives_result(programme_data)["card_narratives"]

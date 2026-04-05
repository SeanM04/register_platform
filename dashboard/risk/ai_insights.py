"""Narrative helpers for the risk dashboard overview cards.

This mirrors the other dashboard AI insight modules:

- always build deterministic rule-based narratives first
- optionally ask Gemini or OpenAI to rewrite the overview copy
- validate and normalize provider responses before the page uses them

The risk page keeps row-level table copy and chart interactions local in the frontend. This
module only owns the overview narratives for the main risk story cards.
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
RISK_CARD_SEVERITIES = {"stable", "medium", "high"}
RISK_CARD_CONFIDENCES = {"low", "medium", "high"}
RISK_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
RISK_CARD_KEYS = ("distribution", "drivers", "levels", "programmes")
RISK_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": list(RISK_CARD_KEYS),
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
                for card_key in RISK_CARD_KEYS
            },
        }
    },
}


def _truncate_text(value, max_length=42):
    """Clamp long programme labels inside compact narrative copy."""

    value = str(value or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length - 3].rstrip()}..."


def build_risk_fact_pack(risk_data):
    """Convert risk aggregates into a compact fact pack for rules and AI prompts."""

    distribution_rows = [
        {
            "label": row.get("label", ""),
            "students": int(row.get("count", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
            "tone": row.get("tone", ""),
        }
        for row in risk_data.get("risk_distribution_rows", [])
        if int(row.get("count", 0) or 0) > 0
    ]
    driver_rows = [
        {
            "label": row.get("label", ""),
            "students": int(row.get("count", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in risk_data.get("risk_driver_rows", [])[:8]
        if int(row.get("count", 0) or 0) > 0
    ]
    level_rows = [
        {
            "level": row.get("level", ""),
            "students": int(row.get("total", 0) or 0),
            "high_risk": int(row.get("high_risk", 0) or 0),
            "medium_risk": int(row.get("medium_risk", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in risk_data.get("risk_level_rows", [])
        if int(row.get("total", 0) or 0) > 0
    ]
    programme_rows = [
        {
            "programme": row.get("programme", ""),
            "students": int(row.get("total", 0) or 0),
            "high_risk": int(row.get("high_risk", 0) or 0),
            "medium_risk": int(row.get("medium_risk", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in risk_data.get("risk_programme_rows", [])
        if int(row.get("total", 0) or 0) > 0
    ]

    distribution_rows.sort(key=lambda row: (-row["students"], row["label"]))

    return {
        "students_total": int(risk_data.get("total_students", 0) or 0),
        "watchlist_total": int(risk_data.get("at_risk_students", 0) or 0),
        "watchlist_share_pct": int(risk_data.get("watchlist_share_pct", 0) or 0),
        "high_risk_total": int(risk_data.get("high_risk_count", 0) or 0),
        "medium_risk_total": int(risk_data.get("medium_risk_count", 0) or 0),
        "critical_total": int(risk_data.get("critical_count", 0) or 0),
        "multi_fail_total": int(risk_data.get("multi_fail_count", 0) or 0),
        "distribution": {
            "bands": distribution_rows,
            "lead_band": distribution_rows[0]["label"] if distribution_rows else "",
        },
        "drivers": {
            "items": driver_rows,
            "lead_driver": driver_rows[0]["label"] if driver_rows else "",
            "lead_driver_students": driver_rows[0]["students"] if driver_rows else 0,
        },
        "levels": {
            "items": level_rows,
            "lead_level": level_rows[0]["level"] if level_rows else "",
            "lead_level_students": level_rows[0]["students"] if level_rows else 0,
        },
        "programmes": {
            "items": programme_rows,
            "lead_programme": programme_rows[0]["programme"] if programme_rows else "",
            "lead_programme_students": programme_rows[0]["students"] if programme_rows else 0,
        },
    }


def _resolve_distribution_severity(facts):
    watchlist_total = int(facts.get("watchlist_total", 0) or 0)
    watchlist_share_pct = int(facts.get("watchlist_share_pct", 0) or 0)
    critical_total = int(facts.get("critical_total", 0) or 0)
    high_risk_total = int(facts.get("high_risk_total", 0) or 0)

    if watchlist_total == 0:
        return "stable"
    if critical_total > 0 or (high_risk_total >= 12 and watchlist_share_pct >= 18):
        return "high"
    if high_risk_total > 0 or watchlist_share_pct >= 10:
        return "medium"
    return "stable"


def _resolve_distribution_confidence(facts):
    students_total = int(facts.get("students_total", 0) or 0)
    if students_total >= 160:
        return "high"
    if students_total >= 50:
        return "medium"
    return "low"


def _resolve_driver_severity(facts):
    lead_driver_students = int(facts["drivers"].get("lead_driver_students", 0) or 0)
    watchlist_total = int(facts.get("watchlist_total", 0) or 0)
    if watchlist_total == 0:
        return "stable"
    if lead_driver_students >= 12 and watchlist_total >= 18:
        return "high"
    if lead_driver_students >= 4:
        return "medium"
    return "stable"


def _resolve_driver_confidence(facts):
    driver_count = len(facts["drivers"]["items"])
    watchlist_total = int(facts.get("watchlist_total", 0) or 0)
    if driver_count >= 4 and watchlist_total >= 18:
        return "high"
    if driver_count >= 2 and watchlist_total >= 6:
        return "medium"
    return "low"


def _resolve_level_severity(facts):
    lead_students = int(facts["levels"].get("lead_level_students", 0) or 0)
    high_risk_total = int(facts.get("high_risk_total", 0) or 0)
    if lead_students == 0:
        return "stable"
    if lead_students >= 10 and high_risk_total >= 4:
        return "high"
    if lead_students >= 4:
        return "medium"
    return "stable"


def _resolve_level_confidence(facts):
    level_count = len(facts["levels"]["items"])
    watchlist_total = int(facts.get("watchlist_total", 0) or 0)
    if level_count >= 4 and watchlist_total >= 16:
        return "high"
    if level_count >= 2 and watchlist_total >= 6:
        return "medium"
    return "low"


def _resolve_programme_severity(facts):
    lead_students = int(facts["programmes"].get("lead_programme_students", 0) or 0)
    watchlist_total = int(facts.get("watchlist_total", 0) or 0)
    if lead_students == 0:
        return "stable"
    if lead_students >= 10 and watchlist_total >= 18:
        return "high"
    if lead_students >= 4:
        return "medium"
    return "stable"


def _resolve_programme_confidence(facts):
    programme_count = len(facts["programmes"]["items"])
    watchlist_total = int(facts.get("watchlist_total", 0) or 0)
    if programme_count >= 4 and watchlist_total >= 16:
        return "high"
    if programme_count >= 2 and watchlist_total >= 6:
        return "medium"
    return "low"


def build_rule_based_risk_narratives(risk_data):
    """Build deterministic overview narratives and safe severity/confidence baselines."""

    facts = build_risk_fact_pack(risk_data)
    distribution_rows = facts["distribution"]["bands"]
    driver_rows = facts["drivers"]["items"]
    level_rows = facts["levels"]["items"]
    programme_rows = facts["programmes"]["items"]

    if facts["watchlist_total"]:
        leading_band = distribution_rows[0] if distribution_rows else None
        if facts["critical_total"]:
            distribution_insight = (
                f"{facts['critical_total']} student{'s' if facts['critical_total'] != 1 else ''} are already in the critical risk band, "
                f"with {facts['high_risk_total']} high-risk cases in the current scope."
            )
        elif leading_band:
            distribution_insight = (
                f"{facts['watchlist_total']} student{'s' if facts['watchlist_total'] != 1 else ''} currently sit on the watchlist, "
                f"and {leading_band['label']} is the largest visible severity band."
            )
        else:
            distribution_insight = (
                f"{facts['watchlist_total']} student{'s' if facts['watchlist_total'] != 1 else ''} currently sit on the watchlist "
                "in the filtered cohort."
            )
        distribution_action = (
            "Action: Start with the distribution chart to see whether the current watchlist is mostly moderate pressure or already concentrated in high-risk cases."
        )
    else:
        distribution_insight = "No at-risk students are visible for the current filters."
        distribution_action = "Action: Use the current filters to isolate a smaller cohort if you want to stress-test the watchlist view."

    if driver_rows:
        lead_driver = driver_rows[0]
        runner_up = driver_rows[1] if len(driver_rows) > 1 else None
        if runner_up:
            drivers_insight = (
                f"{lead_driver['label']} is the strongest visible watchlist driver, ahead of {runner_up['label']} across the flagged cohort."
            )
        else:
            drivers_insight = f"{lead_driver['label']} is the clearest visible risk driver in the current watchlist."
        drivers_action = "Action: Use the driver chart to separate academic performance problems from decision or carrying pressure before opening the register."
    else:
        drivers_insight = "No shared watchlist driver pattern is visible for the current filters."
        drivers_action = "Action: Adjust the current filters to bring a visible driver pattern back into view."

    if level_rows:
        lead_level = level_rows[0]
        levels_insight = (
            f"{lead_level['level']} currently holds the largest at-risk cluster, with {lead_level['high_risk']} high-risk and "
            f"{lead_level['medium_risk']} medium-risk student{'s' if lead_level['students'] != 1 else ''}."
        )
        levels_action = "Action: Use the academic-level split to see where intervention load is building before you review individual students."
    else:
        levels_insight = "No academic-level concentration is visible for the current watchlist."
        levels_action = "Action: Adjust the current filters to bring level concentration back into view."

    if programme_rows:
        lead_programme = programme_rows[0]
        programme_name = _truncate_text(lead_programme["programme"], 32)
        programmes_insight = (
            f"{programme_name} carries the largest flagged programme cluster, with {lead_programme['students']} watchlist student"
            f"{'s' if lead_programme['students'] != 1 else ''} in the current scope."
        )
        programmes_action = "Action: Use programme concentration to decide where the next support clinic or advising block will have the biggest effect."
    else:
        programmes_insight = "No programme concentration is visible for the current watchlist."
        programmes_action = "Action: Adjust the current filters to bring programme-level pressure back into view."

    return {
        "source": "rules",
        "cards": {
            "distribution": {
                "insight": distribution_insight,
                "action": distribution_action,
                "severity": _resolve_distribution_severity(facts),
                "confidence": _resolve_distribution_confidence(facts),
            },
            "drivers": {
                "insight": drivers_insight,
                "action": drivers_action,
                "severity": _resolve_driver_severity(facts),
                "confidence": _resolve_driver_confidence(facts),
            },
            "levels": {
                "insight": levels_insight,
                "action": levels_action,
                "severity": _resolve_level_severity(facts),
                "confidence": _resolve_level_confidence(facts),
            },
            "programmes": {
                "insight": programmes_insight,
                "action": programmes_action,
                "severity": _resolve_programme_severity(facts),
                "confidence": _resolve_programme_confidence(facts),
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


def _normalize_ai_narrative_payload(payload, source, fallback_cards=None):
    """Validate and normalize provider output into the risk card contract."""

    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}
    for card_key in RISK_CARD_KEYS:
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")
        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in RISK_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in RISK_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in RISK_CARD_SEVERITIES
            and RISK_CARD_SEVERITY_RANK[severity] < RISK_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity
        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in RISK_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in RISK_CARD_CONFIDENCES else "medium"
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
        "You generate concise dashboard narratives for a university student-risk analytics page.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "Use exact labels from the facts where helpful.\n"
        "If the facts show no issue, the action should suggest monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


@lru_cache(maxsize=64)
def _request_risk_openai_narratives(fact_pack_json):
    """Request risk narratives from OpenAI for a single fact-pack snapshot."""

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
                    "name": "risk_card_narratives",
                    "schema": RISK_NARRATIVE_SCHEMA,
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
def _request_risk_google_narratives(fact_pack_json):
    """Request risk narratives from Gemini for a single fact-pack snapshot."""

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
            "responseJsonSchema": RISK_NARRATIVE_SCHEMA,
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


def get_risk_card_narratives(risk_data):
    """Return overview card narratives for the risk dashboard page."""

    fallback = build_rule_based_risk_narratives(risk_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        return fallback

    fact_pack_json = json.dumps(build_risk_fact_pack(risk_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            raw_response = _request_risk_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            return _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"])
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after Google risk narrative request failed: %s", error)
            if provider == "google":
                return fallback

    if provider in {"auto", "openai"}:
        if provider == "openai" and not getattr(settings, "OPENAI_API_KEY", ""):
            logger.info("AI_INSIGHTS_PROVIDER is openai but OPENAI_API_KEY is missing; using rule-based risk narratives.")
            return fallback
        if provider == "auto" and not getattr(settings, "OPENAI_INSIGHTS_ENABLED", False):
            return fallback
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return fallback

        try:
            raw_response = _request_risk_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Responses API.")
            return _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"])
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after OpenAI risk narrative request failed: %s", error)

    return fallback

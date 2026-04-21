"""Narrative helpers for the institutional insights dashboard overview cards."""

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache

from django.conf import settings

from .constants import INSIGHT_CARD_KEYS


logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
GOOGLE_GENERATE_CONTENT_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
INSIGHT_CARD_SEVERITIES = {"stable", "medium", "high"}
INSIGHT_CARD_CONFIDENCES = {"low", "medium", "high"}
INSIGHT_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
INSIGHT_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": list(INSIGHT_CARD_KEYS),
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
                for card_key in INSIGHT_CARD_KEYS
            },
        }
    },
}


def build_insight_fact_pack(insights_data):
    """Convert the insights page aggregates into a compact prompt-ready fact pack."""

    distribution_rows = [
        {
            "label": row.get("label", ""),
            "students": int(row.get("count", 0) or 0),
            "share_pct": int(row.get("percent", 0) or 0),
        }
        for row in insights_data.get("risk_distribution_rows", [])
        if int(row.get("count", 0) or 0) > 0
    ]
    faculty_load_rows = [
        {
            "faculty": row.get("label", ""),
            "registrations": int(row.get("registrations", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in insights_data.get("faculty_load_rows", [])
        if int(row.get("registrations", 0) or 0) > 0
    ]
    faculty_pressure_rows = [
        {
            "faculty": row.get("label", ""),
            "students": int(row.get("total", 0) or 0),
            "high_risk": int(row.get("high_risk", 0) or 0),
            "medium_risk": int(row.get("medium_risk", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in insights_data.get("faculty_pressure_rows", [])
        if int(row.get("total", 0) or 0) > 0
    ]
    driver_rows = [
        {
            "label": row.get("label", ""),
            "students": int(row.get("count", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in insights_data.get("driver_rows", [])
        if int(row.get("count", 0) or 0) > 0
    ]

    return {
        "students_total": int(insights_data.get("total_students", 0) or 0),
        "registrations_total": int(insights_data.get("total_registrations", 0) or 0),
        "at_risk_total": int(insights_data.get("flagged_total", 0) or 0),
        "high_risk_total": int(insights_data.get("high_risk_total", 0) or 0),
        "medium_risk_total": int(insights_data.get("medium_risk_total", 0) or 0),
        "retention_rate": int(insights_data.get("retention_rate", 0) or 0),
        "watchlist_share_pct": int(insights_data.get("watchlist_share_pct", 0) or 0),
        "distribution": {
            "bands": distribution_rows,
            "lead_band": distribution_rows[0]["label"] if distribution_rows else "",
        },
        "faculty_load": {
            "items": faculty_load_rows,
            "lead_faculty": faculty_load_rows[0]["faculty"] if faculty_load_rows else "",
            "lead_share_pct": faculty_load_rows[0]["share_pct"] if faculty_load_rows else 0,
        },
        "faculty_pressure": {
            "items": faculty_pressure_rows,
            "lead_faculty": faculty_pressure_rows[0]["faculty"] if faculty_pressure_rows else "",
            "lead_students": faculty_pressure_rows[0]["students"] if faculty_pressure_rows else 0,
        },
        "drivers": {
            "items": driver_rows,
            "lead_driver": driver_rows[0]["label"] if driver_rows else "",
            "lead_driver_students": driver_rows[0]["students"] if driver_rows else 0,
        },
    }


def _resolve_distribution_severity(facts):
    if facts["at_risk_total"] == 0:
        return "stable"
    if facts["high_risk_total"] >= 12 or facts["watchlist_share_pct"] >= 18:
        return "high"
    if facts["high_risk_total"] > 0 or facts["watchlist_share_pct"] >= 8:
        return "medium"
    return "stable"


def _resolve_distribution_confidence(facts):
    if facts["students_total"] >= 160:
        return "high"
    if facts["students_total"] >= 50:
        return "medium"
    return "low"


def _resolve_faculty_load_severity(facts):
    lead_share_pct = int(facts["faculty_load"].get("lead_share_pct", 0) or 0)
    if lead_share_pct >= 50:
        return "high"
    if lead_share_pct >= 35:
        return "medium"
    return "stable"


def _resolve_faculty_load_confidence(facts):
    faculty_count = len(facts["faculty_load"]["items"])
    registrations_total = int(facts.get("registrations_total", 0) or 0)
    if faculty_count >= 4 and registrations_total >= 100:
        return "high"
    if faculty_count >= 2 and registrations_total >= 20:
        return "medium"
    return "low"


def _resolve_faculty_pressure_severity(facts):
    lead_students = int(facts["faculty_pressure"].get("lead_students", 0) or 0)
    if lead_students >= 10 and int(facts.get("high_risk_total", 0) or 0) >= 4:
        return "high"
    if lead_students >= 4:
        return "medium"
    return "stable"


def _resolve_faculty_pressure_confidence(facts):
    faculty_count = len(facts["faculty_pressure"]["items"])
    at_risk_total = int(facts.get("at_risk_total", 0) or 0)
    if faculty_count >= 3 and at_risk_total >= 16:
        return "high"
    if faculty_count >= 2 and at_risk_total >= 6:
        return "medium"
    return "low"


def _resolve_driver_severity(facts):
    lead_driver_students = int(facts["drivers"].get("lead_driver_students", 0) or 0)
    if lead_driver_students >= 10 and int(facts.get("at_risk_total", 0) or 0) >= 18:
        return "high"
    if lead_driver_students >= 4:
        return "medium"
    return "stable"


def _resolve_driver_confidence(facts):
    driver_count = len(facts["drivers"]["items"])
    at_risk_total = int(facts.get("at_risk_total", 0) or 0)
    if driver_count >= 4 and at_risk_total >= 18:
        return "high"
    if driver_count >= 2 and at_risk_total >= 6:
        return "medium"
    return "low"


def build_rule_based_insight_narratives(insights_data):
    """Build deterministic overview narratives for the insights story cards."""

    facts = build_insight_fact_pack(insights_data)
    lead_band = facts["distribution"]["lead_band"]
    lead_faculty = facts["faculty_load"]["lead_faculty"]
    lead_pressure_faculty = facts["faculty_pressure"]["lead_faculty"]
    lead_driver = facts["drivers"]["lead_driver"]

    if facts["at_risk_total"]:

        distribution_insight = (
    f"{facts['at_risk_total']} students currently sit on the institutional watchlist, "
    f"with {lead_band or 'the visible risk mix'} leading the current distribution. "
   
        )
        
        distribution_action = (
            "Action: Start with the distribution chart to separate stable cohort volume from the current intervention queue."
        )
    else:
        distribution_insight = "No students are currently on the watchlist for the active insight scope."
        distribution_action = "Action: Keep monitoring the distribution view as new filtered data arrives."

    if lead_faculty:
        faculty_load_insight = (
            f"{lead_faculty} carries the heaviest visible registration load at {facts['faculty_load']['lead_share_pct']}% of the current scope."
        )
        faculty_load_action = (
            "Action: Use faculty load to decide where advising, classroom, and support capacity may need rebalancing first."
        )
    else:
        faculty_load_insight = "No faculty load pattern is visible for the current filters."
        faculty_load_action = "Action: Adjust the current filters to bring faculty concentration back into view."

    if lead_pressure_faculty:
        faculty_pressure_insight = (
            f"{lead_pressure_faculty} carries the largest flagged-student cluster, making it the clearest pressure point for intervention planning."
        )
        faculty_pressure_action = (
            "Action: Compare high-risk versus medium-risk mix by faculty before assigning the next support block."
        )
    else:
        faculty_pressure_insight = "No flagged-student concentration by faculty is visible for the current scope."
        faculty_pressure_action = "Action: Recheck the filters if you need a faculty-level pressure comparison."

    if lead_driver:
        driver_insight = (
            f"{lead_driver} is the strongest recurring watchlist driver across the visible flagged cohort."
        )
        driver_action = (
            "Action: Anchor the next intervention cycle on the lead driver before opening student-level follow-up."
        )
    else:
        driver_insight = "No recurring driver pattern is visible for the current flagged cohort."
        driver_action = "Action: Keep interventions case-by-case until a clearer shared driver emerges."

    return {
        "source": "rules",
        "cards": {
            "distribution": {
                "insight": distribution_insight,
                "action": distribution_action,
                "severity": _resolve_distribution_severity(facts),
                "confidence": _resolve_distribution_confidence(facts),
            },
            "faculty_load": {
                "insight": faculty_load_insight,
                "action": faculty_load_action,
                "severity": _resolve_faculty_load_severity(facts),
                "confidence": _resolve_faculty_load_confidence(facts),
            },
            "faculty_pressure": {
                "insight": faculty_pressure_insight,
                "action": faculty_pressure_action,
                "severity": _resolve_faculty_pressure_severity(facts),
                "confidence": _resolve_faculty_pressure_confidence(facts),
            },
            "drivers": {
                "insight": driver_insight,
                "action": driver_action,
                "severity": _resolve_driver_severity(facts),
                "confidence": _resolve_driver_confidence(facts),
            },
        },
    }


def _extract_response_text(response_payload):
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in response_payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    return ""


def _extract_google_response_text(response_payload):
    for candidate in response_payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if isinstance(part.get("text"), str) and part["text"].strip():
                return part["text"]
    return ""


def _normalize_ai_narrative_payload(payload, source, fallback_cards=None):
    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}

    for card_key in INSIGHT_CARD_KEYS:
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")

        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in INSIGHT_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in INSIGHT_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in INSIGHT_CARD_SEVERITIES
            and INSIGHT_CARD_SEVERITY_RANK[severity] < INSIGHT_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity

        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in INSIGHT_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in INSIGHT_CARD_CONFIDENCES else "medium"

        normalized_cards[card_key] = {
            "insight": insight,
            "action": action,
            "severity": severity,
            "confidence": confidence,
        }

    return {"source": source, "cards": normalized_cards}


def _build_narrative_prompt(fact_pack_json):
    return (
        "You generate concise executive dashboard narratives for a university institutional insights page.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "Use exact labels from the facts where helpful.\n"
        "If the facts show no issue, the action should suggest monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


@lru_cache(maxsize=64)
def _request_insight_openai_narratives(fact_pack_json):
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
                    "name": "insight_card_narratives",
                    "schema": INSIGHT_NARRATIVE_SCHEMA,
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
def _request_insight_google_narratives(fact_pack_json):
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
            "responseJsonSchema": INSIGHT_NARRATIVE_SCHEMA,
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


def get_insight_card_narratives(insights_data):
    """Return overview card narratives for the institutional insights page."""

    fallback = build_rule_based_insight_narratives(insights_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        return fallback

    fact_pack_json = json.dumps(build_insight_fact_pack(insights_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            raw_response = _request_insight_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            return _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"])
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after Google insights narrative request failed: %s", error)
            if provider == "google":
                return fallback

    if provider in {"auto", "openai"}:
        if provider == "openai" and not getattr(settings, "OPENAI_API_KEY", ""):
            logger.info("AI_INSIGHTS_PROVIDER is openai but OPENAI_API_KEY is missing; using rule-based insights narratives.")
            return fallback
        if provider == "auto" and not getattr(settings, "OPENAI_INSIGHTS_ENABLED", False):
            return fallback
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return fallback

        try:
            raw_response = _request_insight_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Responses API.")
            return _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"])
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after OpenAI insights narrative request failed: %s", error)

    return fallback

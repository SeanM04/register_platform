"""Narrative helpers for the landing dashboard overview cards.

This mirrors the AI overview pattern used on the specialist pages:

- always build deterministic rule-based narratives first
- optionally ask Gemini or OpenAI to rewrite the overview copy
- validate and normalize provider responses before the page uses them

The landing page keeps its hero banner and route cards deterministic. This module only
owns the overview narratives for the four chart cards:

- ``outcomes``
- ``risk``
- ``faculty``
- ``progress``
"""

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache
from hashlib import sha256

from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
GOOGLE_GENERATE_CONTENT_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OVERVIEW_CARD_SEVERITIES = {"stable", "medium", "high"}
OVERVIEW_CARD_CONFIDENCES = {"low", "medium", "high"}
OVERVIEW_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
OVERVIEW_CARD_KEYS = ("outcomes", "risk", "faculty", "progress")
OVERVIEW_AI_CACHE_TTL_SECONDS = 600
OVERVIEW_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": list(OVERVIEW_CARD_KEYS),
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
                for card_key in OVERVIEW_CARD_KEYS
            },
        }
    },
}


def _format_count(value):
    """Format counts with grouping so narrative copy stays readable."""

    return f"{int(value or 0):,}"


def _truncate_text(value, max_length=42):
    """Clamp long labels so overview copy remains compact on the landing page."""

    value = str(value or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length - 3].rstrip()}..."


def build_overview_fact_pack(overview_data):
    """Convert landing-page aggregates into a compact fact pack for AI prompts."""

    outcome_rows = [
        {
            "key": row.get("key", ""),
            "label": row.get("label", ""),
            "count": int(row.get("count", 0) or 0),
            "percent": int(row.get("percent", 0) or 0),
        }
        for row in overview_data.get("outcome_rows", [])
        if int(row.get("count", 0) or 0) > 0
    ]
    risk_rows = [
        {
            "key": row.get("key", ""),
            "label": row.get("label", ""),
            "count": int(row.get("count", 0) or 0),
            "percent": int(row.get("percent", 0) or 0),
        }
        for row in overview_data.get("risk_distribution_rows", [])
        if int(row.get("count", 0) or 0) > 0
    ]
    faculty_rows = [
        {
            "label": row.get("label", ""),
            "registrations": int(row.get("registrations", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in overview_data.get("faculty_load_rows", [])
        if int(row.get("registrations", 0) or 0) > 0
    ]
    progress_rows = [
        {
            "key": row.get("key", ""),
            "label": row.get("label", ""),
            "count": int(row.get("count", 0) or 0),
            "share_pct": int(row.get("share_pct", 0) or 0),
        }
        for row in overview_data.get("progress_rows", [])
        if int(row.get("count", 0) or 0) > 0
    ]

    outcome_rows.sort(key=lambda row: (-row["count"], row["label"]))
    risk_rows.sort(key=lambda row: (-row["count"], row["label"]))
    faculty_rows.sort(key=lambda row: (-row["registrations"], row["label"]))
    progress_rows.sort(key=lambda row: (-row["count"], row["label"]))

    passed_row = next((row for row in outcome_rows if row["key"] == "passed"), None)
    failed_row = next((row for row in outcome_rows if row["key"] == "failed"), None)
    awaiting_row = next((row for row in outcome_rows if row["key"] == "awaiting"), None)
    marked_results_total = int((passed_row or {}).get("count", 0) or 0) + int((failed_row or {}).get("count", 0) or 0)
    outcome_total = sum(row["count"] for row in outcome_rows)
    pass_rate_pct = round((int((passed_row or {}).get("count", 0) or 0) / marked_results_total) * 100) if marked_results_total else 0

    critical_row = next((row for row in risk_rows if row["key"] == "critical"), None)
    high_row = next((row for row in risk_rows if row["key"] == "high"), None)
    moderate_row = next((row for row in risk_rows if row["key"] == "moderate"), None)
    stable_row = next((row for row in risk_rows if row["key"] == "stable"), None)
    students_total = sum(row["count"] for row in risk_rows)
    hot_risk_total = int((critical_row or {}).get("count", 0) or 0) + int((high_row or {}).get("count", 0) or 0)
    hot_risk_share_pct = round((hot_risk_total / students_total) * 100) if students_total else 0

    lead_faculty = faculty_rows[0] if faculty_rows else None
    runner_up_faculty = faculty_rows[1] if len(faculty_rows) > 1 else None
    registrations_total = sum(row["registrations"] for row in faculty_rows)

    proceed_row = next((row for row in progress_rows if row["key"] == "proceed"), None)
    retake_row = next((row for row in progress_rows if row["key"] == "retake"), None)
    pending_row = next((row for row in progress_rows if row["key"] == "pending"), None)
    exit_row = next((row for row in progress_rows if row["key"] == "exit"), None)

    return {
        "students_total": students_total,
        "registrations_total": registrations_total,
        "results_total": outcome_total,
        "marked_results_total": marked_results_total,
        "outcomes": {
            "visible_statuses": len(outcome_rows),
            "lead_label": outcome_rows[0]["label"] if outcome_rows else "",
            "passed_count": int((passed_row or {}).get("count", 0) or 0),
            "failed_count": int((failed_row or {}).get("count", 0) or 0),
            "awaiting_count": int((awaiting_row or {}).get("count", 0) or 0),
            "pass_rate_pct": pass_rate_pct,
            "awaiting_share_pct": int((awaiting_row or {}).get("percent", 0) or 0),
            "failed_share_pct": int((failed_row or {}).get("percent", 0) or 0),
        },
        "risk": {
            "visible_bands": len(risk_rows),
            "lead_band": risk_rows[0]["label"] if risk_rows else "",
            "critical_total": int((critical_row or {}).get("count", 0) or 0),
            "high_total": int((high_row or {}).get("count", 0) or 0),
            "moderate_total": int((moderate_row or {}).get("count", 0) or 0),
            "stable_total": int((stable_row or {}).get("count", 0) or 0),
            "stable_share_pct": int((stable_row or {}).get("percent", 0) or 0),
            "hot_risk_total": hot_risk_total,
            "hot_risk_share_pct": hot_risk_share_pct,
        },
        "faculty": {
            "leader": lead_faculty["label"] if lead_faculty else "",
            "leader_registrations": int((lead_faculty or {}).get("registrations", 0) or 0),
            "leader_share_pct": int((lead_faculty or {}).get("share_pct", 0) or 0),
            "runner_up": runner_up_faculty["label"] if runner_up_faculty else "",
            "runner_up_share_pct": int((runner_up_faculty or {}).get("share_pct", 0) or 0),
            "share_gap_pct": (
                int((lead_faculty or {}).get("share_pct", 0) or 0) - int((runner_up_faculty or {}).get("share_pct", 0) or 0)
                if lead_faculty and runner_up_faculty
                else 0
            ),
            "visible_faculties": len(faculty_rows),
        },
        "progress": {
            "visible_states": len(progress_rows),
            "leader": progress_rows[0]["label"] if progress_rows else "",
            "leader_share_pct": int((progress_rows[0] if progress_rows else {}).get("share_pct", 0) or 0),
            "proceed_count": int((proceed_row or {}).get("count", 0) or 0),
            "proceed_share_pct": int((proceed_row or {}).get("share_pct", 0) or 0),
            "retake_count": int((retake_row or {}).get("count", 0) or 0),
            "retake_share_pct": int((retake_row or {}).get("share_pct", 0) or 0),
            "pending_count": int((pending_row or {}).get("count", 0) or 0),
            "pending_share_pct": int((pending_row or {}).get("share_pct", 0) or 0),
            "exit_count": int((exit_row or {}).get("count", 0) or 0),
            "exit_share_pct": int((exit_row or {}).get("share_pct", 0) or 0),
        },
    }


def _resolve_outcome_severity(facts):
    results_total = int(facts.get("results_total", 0) or 0)
    outcomes = facts["outcomes"]
    if results_total == 0:
        return "stable"
    if outcomes["failed_share_pct"] >= 35 or (outcomes["awaiting_share_pct"] >= 30 and results_total >= 60):
        return "high"
    if outcomes["failed_share_pct"] >= 20 or outcomes["awaiting_share_pct"] >= 15:
        return "medium"
    return "stable"


def _resolve_outcome_confidence(facts):
    results_total = int(facts.get("results_total", 0) or 0)
    row_count = int(facts["outcomes"].get("visible_statuses", 0) or 0)
    if results_total >= 300 and row_count >= 2:
        return "high"
    if results_total >= 80 and row_count >= 1:
        return "medium"
    return "low"


def _resolve_risk_severity(facts):
    risk = facts["risk"]
    students_total = int(facts.get("students_total", 0) or 0)
    if students_total == 0:
        return "stable"
    if risk["critical_total"] > 0 or (risk["hot_risk_share_pct"] >= 18 and students_total >= 80):
        return "high"
    if risk["hot_risk_total"] > 0 or risk["moderate_total"] >= max(round(students_total * 0.18), 12):
        return "medium"
    return "stable"


def _resolve_risk_confidence(facts):
    students_total = int(facts.get("students_total", 0) or 0)
    row_count = int(facts["risk"].get("visible_bands", 0) or 0)
    if students_total >= 160 and row_count >= 3:
        return "high"
    if students_total >= 50 and row_count >= 2:
        return "medium"
    return "low"


def _resolve_faculty_severity(facts):
    faculty = facts["faculty"]
    registrations_total = int(facts.get("registrations_total", 0) or 0)
    if registrations_total == 0 or not faculty["visible_faculties"]:
        return "stable"
    if faculty["leader_share_pct"] >= 40 or faculty["share_gap_pct"] >= 15:
        return "high"
    if faculty["leader_share_pct"] >= 28 or faculty["share_gap_pct"] >= 8:
        return "medium"
    return "stable"


def _resolve_faculty_confidence(facts):
    registrations_total = int(facts.get("registrations_total", 0) or 0)
    visible_faculties = int(facts["faculty"].get("visible_faculties", 0) or 0)
    if registrations_total >= 500 and visible_faculties >= 3:
        return "high"
    if registrations_total >= 120 and visible_faculties >= 2:
        return "medium"
    return "low"


def _resolve_progress_severity(facts):
    progress = facts["progress"]
    registrations_total = int(facts.get("registrations_total", 0) or 0)
    if registrations_total == 0 or not progress["visible_states"]:
        return "stable"
    rework_share_pct = progress["retake_share_pct"] + progress["pending_share_pct"] + progress["exit_share_pct"]
    if progress["pending_share_pct"] >= 35 or progress["exit_share_pct"] >= 12:
        return "high"
    if rework_share_pct >= 25 or progress["exit_count"] > 0:
        return "medium"
    return "stable"


def _resolve_progress_confidence(facts):
    registrations_total = int(facts.get("registrations_total", 0) or 0)
    row_count = int(facts["progress"].get("visible_states", 0) or 0)
    if registrations_total >= 500 and row_count >= 3:
        return "high"
    if registrations_total >= 120 and row_count >= 2:
        return "medium"
    return "low"


def build_rule_based_overview_narratives(overview_data):
    """Build deterministic overview narratives and safe severity/confidence baselines."""

    facts = build_overview_fact_pack(overview_data)
    outcomes = facts["outcomes"]
    risk = facts["risk"]
    faculty = facts["faculty"]
    progress = facts["progress"]

    if facts["results_total"]:
        if outcomes["awaiting_count"]:
            outcomes_insight = (
                f"Passed results currently represent {outcomes['pass_rate_pct']}% of marked outcomes, with "
                f"{_format_count(outcomes['awaiting_count'])} results still awaiting marks."
            )
        elif facts["marked_results_total"]:
            outcomes_insight = (
                f"Passed results currently represent {outcomes['pass_rate_pct']}% of the visible marked assessment picture."
            )
        else:
            outcomes_insight = "Visible assessment results are still waiting to be marked in the current scope."
        outcomes_action = "Use the outcome donut first to separate academic health from marking backlog before opening a specialist page."
    else:
        outcomes_insight = "No assessment outcome story is available for the current filters."
        outcomes_action = "Adjust the current filters to bring the visible assessment picture back into view."

    if facts["students_total"]:
        if risk["hot_risk_total"]:
            risk_insight = (
                f"{_format_count(risk['hot_risk_total'])} students currently sit in the high or critical bands, while "
                f"{risk['stable_share_pct']}% of the cohort remains stable."
            )
        elif risk["moderate_total"]:
            risk_insight = (
                f"The visible cohort is mostly stable, but {_format_count(risk['moderate_total'])} students are already in the moderate watch band."
            )
        else:
            risk_insight = "The visible cohort currently sits outside the moderate, high, and critical watch bands."
        risk_action = "Use the risk mix first to judge whether the landing-page story is still preventive work or already urgent intervention."
    else:
        risk_insight = "No student risk story is available for the current filters."
        risk_action = "Adjust the current filters to bring the visible risk distribution back into view."

    if faculty["visible_faculties"]:
        if faculty["runner_up"]:
            faculty_insight = (
                f"{faculty['leader']} currently carries {faculty['leader_share_pct']}% of visible registrations, ahead of {faculty['runner_up']}."
            )
        else:
            faculty_insight = f"{faculty['leader']} currently carries the visible registration load in the active scope."
        faculty_action = "Use faculty load as the quick capacity signal before opening the deeper insights workspace."
    else:
        faculty_insight = "No faculty load story is available for the current filters."
        faculty_action = "Adjust the current filters to bring visible registration concentration back into view."

    if progress["visible_states"]:
        if progress["pending_count"] and progress["leader"] == "Pending Review":
            progress_insight = (
                f"Pending Review currently represents {progress['pending_share_pct']}% of visible registration decisions."
            )
        elif progress["leader"]:
            progress_insight = (
                f"{progress['leader']} currently leads the visible registration decision picture at {progress['leader_share_pct']}%."
            )
        else:
            progress_insight = "Registration decisions are visible, but no clear momentum pattern is leading the current scope."
        progress_action = "Use the decision chart to judge whether the visible cohort is moving forward or building rework and review pressure."
    else:
        progress_insight = "No registration decision story is available for the current filters."
        progress_action = "Adjust the current filters to bring registration momentum back into view."

    return {
        "source": "rules",
        "cards": {
            "outcomes": {
                "insight": outcomes_insight,
                "action": outcomes_action,
                "severity": _resolve_outcome_severity(facts),
                "confidence": _resolve_outcome_confidence(facts),
            },
            "risk": {
                "insight": risk_insight,
                "action": risk_action,
                "severity": _resolve_risk_severity(facts),
                "confidence": _resolve_risk_confidence(facts),
            },
            "faculty": {
                "insight": faculty_insight,
                "action": faculty_action,
                "severity": _resolve_faculty_severity(facts),
                "confidence": _resolve_faculty_confidence(facts),
            },
            "progress": {
                "insight": progress_insight,
                "action": progress_action,
                "severity": _resolve_progress_severity(facts),
                "confidence": _resolve_progress_confidence(facts),
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
    """Validate and normalize provider output into the overview card contract."""

    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}
    for card_key in OVERVIEW_CARD_KEYS:
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")
        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in OVERVIEW_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in OVERVIEW_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in OVERVIEW_CARD_SEVERITIES
            and OVERVIEW_CARD_SEVERITY_RANK[severity] < OVERVIEW_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity
        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in OVERVIEW_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in OVERVIEW_CARD_CONFIDENCES else "medium"
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
        "You generate concise dashboard narratives for a university landing-page analytics dashboard.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "Use exact labels from the facts where helpful.\n"
        "If the facts show no issue, the action should suggest monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


def _overview_openai_is_enabled():
    """Return whether OpenAI narratives are allowed for overview cards."""

    return bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )


def _build_overview_ai_cache_key(fact_pack_json, source):
    """Build a stable cache key for a normalized AI narrative response."""

    digest = sha256(fact_pack_json.encode("utf-8")).hexdigest()
    return f"dashboard:overview:ai-narratives:{source}:{digest}"


def _get_cached_overview_ai_narratives(fact_pack_json, source):
    """Return a cached AI narrative payload when one is already available."""

    cached_payload = cache.get(_build_overview_ai_cache_key(fact_pack_json, source))
    if not isinstance(cached_payload, dict):
        return None
    if cached_payload.get("source") != source or not isinstance(cached_payload.get("cards"), dict):
        return None
    return cached_payload


def _cache_overview_ai_narratives(fact_pack_json, narratives):
    """Persist a successful AI narrative payload for quick reuse on the same scope."""

    source = str(narratives.get("source", "")).strip().lower()
    if source not in {"google", "openai"}:
        return narratives
    cache.set(
        _build_overview_ai_cache_key(fact_pack_json, source),
        narratives,
        OVERVIEW_AI_CACHE_TTL_SECONDS,
    )
    return narratives


@lru_cache(maxsize=64)
def _request_overview_openai_narratives(fact_pack_json):
    """Request landing-page narratives from OpenAI for a single fact-pack snapshot."""

    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "model": settings.OPENAI_INSIGHTS_MODEL,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 480,
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
                    "name": "overview_card_narratives",
                    "schema": OVERVIEW_NARRATIVE_SCHEMA,
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
def _request_overview_google_narratives(fact_pack_json):
    """Request landing-page narratives from Gemini for a single fact-pack snapshot."""

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
            "maxOutputTokens": 480,
            "responseMimeType": "application/json",
            "responseJsonSchema": OVERVIEW_NARRATIVE_SCHEMA,
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


def get_overview_card_narratives(overview_data):
    """Return overview card narratives for the landing-page dashboard."""

    fallback = build_rule_based_overview_narratives(overview_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = _overview_openai_is_enabled() or bool(getattr(settings, "GOOGLE_API_KEY", ""))
    if provider == "rules" or not insights_enabled:
        return fallback

    fact_pack_json = json.dumps(build_overview_fact_pack(overview_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        cached_google_narratives = _get_cached_overview_ai_narratives(fact_pack_json, "google")
        if cached_google_narratives is not None:
            return cached_google_narratives
        try:
            raw_response = _request_overview_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            normalized_payload = _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"])
            return _cache_overview_ai_narratives(fact_pack_json, normalized_payload)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            cached_google_narratives = _get_cached_overview_ai_narratives(fact_pack_json, "google")
            if cached_google_narratives is not None:
                logger.warning("Reusing cached Google overview narratives after live request failed: %s", error)
                return cached_google_narratives
            logger.warning("Falling back after Google overview narrative request failed: %s", error)
            if provider == "google":
                return fallback

    if provider in {"auto", "openai"}:
        if provider == "openai" and not getattr(settings, "OPENAI_API_KEY", ""):
            logger.info("AI_INSIGHTS_PROVIDER is openai but OPENAI_API_KEY is missing; using rule-based overview narratives.")
            return fallback
        if provider == "auto" and not _overview_openai_is_enabled():
            return fallback
        if not getattr(settings, "OPENAI_API_KEY", ""):
            return fallback

        cached_openai_narratives = _get_cached_overview_ai_narratives(fact_pack_json, "openai")
        if cached_openai_narratives is not None:
            return cached_openai_narratives

        try:
            raw_response = _request_overview_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Responses API.")
            normalized_payload = _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"])
            return _cache_overview_ai_narratives(fact_pack_json, normalized_payload)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            cached_openai_narratives = _get_cached_overview_ai_narratives(fact_pack_json, "openai")
            if cached_openai_narratives is not None:
                logger.warning("Reusing cached OpenAI overview narratives after live request failed: %s", error)
                return cached_openai_narratives
            logger.warning("Falling back after OpenAI overview narrative request failed: %s", error)

    return fallback

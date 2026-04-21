"""AI-assisted and rule-based narratives for the completion dashboard."""

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
GOOGLE_GENERATE_CONTENT_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
COMPLETION_CARD_KEYS = ("cohort", "programme", "drivers")
COMPLETION_CARD_SEVERITIES = {"stable", "medium", "high"}
COMPLETION_CARD_CONFIDENCES = {"low", "medium", "high"}
COMPLETION_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
PROVIDER_LABELS = {
    "google": "Google Gemini",
    "openai": "OpenAI",
    "rules": "Rule-based engine",
    "auto": "Automatic provider selection",
}
COMPLETION_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": list(COMPLETION_CARD_KEYS),
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
                for card_key in COMPLETION_CARD_KEYS
            },
        }
    },
}


def _format_pct(value):
    return f"{round(float(value or 0), 1)}%"


def _format_count(value):
    return f"{int(value or 0):,}"


def _short_programme_name(value):
    return (
        str(value or "").strip()
        .replace("Bachelor of Science", "BSc")
        .replace("Bachelor Of Science", "BSc")
        .replace("Bachelor of Commerce", "BCom")
        .replace("Bachelor Of Commerce", "BCom")
        .replace("Bachelor of Accounting", "BAcc")
        .replace("Bachelor Of Accounting", "BAcc")
        .replace("Bachelor of Engineering", "BEng")
        .replace("Bachelor Of Engineering", "BEng")
        .replace("Honours Degree", "Hons")
    )


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


def _get_provider_label(provider):
    return PROVIDER_LABELS.get(str(provider or "").strip().lower(), "Unknown provider")


def _trim_diagnostic_detail(value, max_length=180):
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - 3].rstrip()}..."


def _classify_provider_error(provider_name, error):
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
                f"{_get_provider_label(provider_key)} timed out before returning completion narratives.",
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
        f"{_get_provider_label(provider_key)} failed unexpectedly while generating completion narratives.",
        detail,
    )


def _build_completion_narrative_diagnostics(
    *,
    configured_provider,
    returned_source,
    status,
    provider_attempted="",
    fallback_reason="",
    message="",
    fallback_detail="",
):
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


def build_completion_fact_pack(completion_data):
    kpis = completion_data.get("kpis", {})
    cohort_rows = sorted(
        completion_data.get("charts", {}).get("cohort_completion", []),
        key=lambda row: (
            float(row.get("completion_rate", 0) or 0),
            int(row.get("effective_cohort_sort_index", 0) or 0),
            int(row.get("progression_period", 0) or 0),
        ),
    )
    programme_rows = sorted(
        completion_data.get("charts", {}).get("programme_completion", []),
        key=lambda row: float(row.get("completion_rate", 0) or 0),
    )
    driver_rows = sorted(
        completion_data.get("charts", {}).get("zero_completion_drivers", []),
        key=lambda row: int(row.get("count", 0) or 0),
        reverse=True,
    )

    strongest_cohort = cohort_rows[-1] if cohort_rows else {}
    weakest_cohort = cohort_rows[0] if cohort_rows else {}
    strongest_programme = programme_rows[-1] if programme_rows else {}
    weakest_programme = programme_rows[0] if programme_rows else {}
    dominant_driver = driver_rows[0] if driver_rows else {}
    total_driver_count = sum(int(row.get("count", 0) or 0) for row in driver_rows)

    return {
        "kpis": {
            "total_students": int(kpis.get("total_students", 0) or 0),
            "effective_cohorts": int(kpis.get("total_cohorts", 0) or 0),
            "average_completion_rate_pct": float(kpis.get("average_completion_rate", 0) or 0),
            "zero_completion_students": int(kpis.get("zero_completion_students", 0) or 0),
            "shifted_students": int(kpis.get("shifted_students", 0) or 0),
        },
        "cohort": {
            "strongest": {
                "cohort": strongest_cohort.get("effective_cohort_label", ""),
                "progression": strongest_cohort.get("progression_label", ""),
                "completion_rate_pct": float(strongest_cohort.get("completion_rate", 0) or 0),
                "zero_completion_count": int(strongest_cohort.get("zero_completion_count", 0) or 0),
            },
            "weakest": {
                "cohort": weakest_cohort.get("effective_cohort_label", ""),
                "progression": weakest_cohort.get("progression_label", ""),
                "completion_rate_pct": float(weakest_cohort.get("completion_rate", 0) or 0),
                "zero_completion_count": int(weakest_cohort.get("zero_completion_count", 0) or 0),
            },
            "rows": [
                {
                    "cohort": row.get("effective_cohort_label", ""),
                    "progression": row.get("progression_label", ""),
                    "completion_rate_pct": float(row.get("completion_rate", 0) or 0),
                    "zero_completion_count": int(row.get("zero_completion_count", 0) or 0),
                }
                for row in cohort_rows[:6]
            ],
        },
        "programme": {
            "strongest": {
                "programme": strongest_programme.get("programme_name", ""),
                "completion_rate_pct": float(strongest_programme.get("completion_rate", 0) or 0),
                "zero_completion_rate_pct": float(strongest_programme.get("zero_completion_rate", 0) or 0),
                "students": int(strongest_programme.get("student_count", 0) or 0),
            },
            "weakest": {
                "programme": weakest_programme.get("programme_name", ""),
                "completion_rate_pct": float(weakest_programme.get("completion_rate", 0) or 0),
                "zero_completion_rate_pct": float(weakest_programme.get("zero_completion_rate", 0) or 0),
                "students": int(weakest_programme.get("student_count", 0) or 0),
            },
            "rows": [
                {
                    "programme": row.get("programme_name", ""),
                    "completion_rate_pct": float(row.get("completion_rate", 0) or 0),
                    "zero_completion_rate_pct": float(row.get("zero_completion_rate", 0) or 0),
                    "students": int(row.get("student_count", 0) or 0),
                }
                for row in programme_rows[-6:]
            ],
        },
        "drivers": {
            "dominant_driver": dominant_driver.get("label", ""),
            "dominant_driver_count": int(dominant_driver.get("count", 0) or 0),
            "dominant_driver_share_pct": round(
                (int(dominant_driver.get("count", 0) or 0) / total_driver_count) * 100,
                1,
            ) if total_driver_count else 0,
            "total_zero_driver_records": total_driver_count,
            "rows": [
                {"label": row.get("label", ""), "count": int(row.get("count", 0) or 0)}
                for row in driver_rows[:6]
            ],
        },
    }


def _resolve_cohort_severity(facts):
    average_rate = float(facts["kpis"].get("average_completion_rate_pct", 0) or 0)
    weakest_rate = float(facts["cohort"]["weakest"].get("completion_rate_pct", 0) or 0)
    if average_rate < 55 or weakest_rate < 35:
        return "high"
    if average_rate < 70 or weakest_rate < 50:
        return "medium"
    return "stable"


def _resolve_programme_severity(facts):
    weakest_rate = float(facts["programme"]["weakest"].get("completion_rate_pct", 0) or 0)
    zero_share = float(facts["programme"]["weakest"].get("zero_completion_rate_pct", 0) or 0)
    if weakest_rate < 55 or zero_share >= 40:
        return "high"
    if weakest_rate < 70 or zero_share >= 20:
        return "medium"
    return "stable"


def _resolve_driver_severity(facts):
    zero_students = int(facts["kpis"].get("zero_completion_students", 0) or 0)
    total_students = max(int(facts["kpis"].get("total_students", 0) or 0), 1)
    shifted_students = int(facts["kpis"].get("shifted_students", 0) or 0)
    zero_share = (zero_students / total_students) * 100
    shifted_share = (shifted_students / total_students) * 100
    if zero_share >= 30 or shifted_share >= 25:
        return "high"
    if zero_share >= 15 or shifted_share >= 12:
        return "medium"
    return "stable"


def build_rule_based_completion_narratives(completion_data):
    facts = build_completion_fact_pack(completion_data)
    strongest_cohort = facts["cohort"]["strongest"]
    weakest_cohort = facts["cohort"]["weakest"]
    strongest_programme = facts["programme"]["strongest"]
    weakest_programme = facts["programme"]["weakest"]
    dominant_driver = facts["drivers"]["dominant_driver"]
    dominant_driver_count = facts["drivers"]["dominant_driver_count"]
    dominant_driver_share = facts["drivers"]["dominant_driver_share_pct"]

    return {
        "source": "rules",
        "cards": {
            "cohort": {
                "insight": (
                    f"{weakest_cohort.get('cohort') or 'The weakest cohort'} at {weakest_cohort.get('progression') or 'the current progression point'} "
                    f"is the clearest cohort pressure point at {_format_pct(weakest_cohort.get('completion_rate_pct'))}."
                    if weakest_cohort.get("cohort")
                    else "No cohort completion narrative is available for the current filters."
                ),
                "action": (
                    f"Review cohorts with the heaviest zero-completion counts first, especially where completion trails "
                    f"{strongest_cohort.get('cohort') or 'the strongest visible cohort'}."
                    if weakest_cohort.get("cohort")
                    else "Adjust the current filters to bring the cohort completion story back into view."
                ),
                "severity": _resolve_cohort_severity(facts),
                "confidence": "low",
            },
            "programme": {
                "insight": (
                    f"{_short_programme_name(strongest_programme.get('programme'))} leads the visible programme set at "
                    f"{_format_pct(strongest_programme.get('completion_rate_pct'))}, while "
                    f"{_short_programme_name(str(weakest_programme.get('programme')))} trails at {_format_pct(weakest_programme.get('completion_rate_pct'))}."
                    if strongest_programme.get("programme") and weakest_programme.get("programme")
                    else "No programme completion narrative is available for the current filters."
                ),
                "action": (
                    f"Use the programme chart to compare the weakest completion programmes first, especially where zero-completion share "
                    f"already sits at {_format_pct(weakest_programme.get('zero_completion_rate_pct'))}."
                    if weakest_programme.get("programme")
                    else "Adjust the current filters to bring the programme completion story back into view."
                ),
                "severity": _resolve_programme_severity(facts),
                "confidence": "low",
            },
            "drivers": {
                "insight": (
                    f"{dominant_driver} currently drives {_format_count(dominant_driver_count)} visible zero-completion records, "
                    f"or {_format_pct(dominant_driver_share)} of the zero-progress cases."
                    if dominant_driver
                    else "No zero-completion driver narrative is available for the current filters."
                ),
                "action": (
                    f"Start with {dominant_driver.lower()} before moving into smaller zero-completion causes across the current scope."
                    if dominant_driver
                    else "Adjust the current filters to bring zero-completion drivers back into view."
                ),
                "severity": _resolve_driver_severity(facts),
                "confidence": "low",
            },
        },
    }


def _normalize_ai_narrative_payload(payload, source, fallback_cards=None):
    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}
    for card_key in COMPLETION_CARD_KEYS:
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")

        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in COMPLETION_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in COMPLETION_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in COMPLETION_CARD_SEVERITIES
            and COMPLETION_CARD_SEVERITY_RANK[severity] < COMPLETION_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity

        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in COMPLETION_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in COMPLETION_CARD_CONFIDENCES else "medium"

        normalized_cards[card_key] = {
            "insight": insight,
            "action": action,
            "severity": severity,
            "confidence": confidence,
        }
    return {"source": source, "cards": normalized_cards}


def _build_narrative_prompt(fact_pack_json):
    return (
        "You generate concise dashboard narratives for a university completion analytics page.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "If the facts show stable performance, the action should recommend monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


@lru_cache(maxsize=64)
def _request_completion_openai_narratives(fact_pack_json):
    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "model": settings.OPENAI_INSIGHTS_MODEL,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 500,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": "Return only structured dashboard narrative fields that match the schema."}],
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
                    "name": "completion_card_narratives",
                    "schema": COMPLETION_NARRATIVE_SCHEMA,
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
def _request_completion_google_narratives(fact_pack_json):
    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "systemInstruction": {
            "parts": [{"text": "Return only structured dashboard narrative fields that match the schema."}]
        },
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500,
            "responseMimeType": "application/json",
            "responseJsonSchema": COMPLETION_NARRATIVE_SCHEMA,
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


def get_completion_card_narratives_result(completion_data):
    fallback = build_rule_based_completion_narratives(completion_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        fallback_reason = "provider_rules_configured" if provider == "rules" else "ai_insights_disabled"
        message = (
            "Completion narratives are using the rule-based engine because AI provider mode is set to rules."
            if provider == "rules"
            else "Completion narratives are using the rule-based engine because AI insights are disabled."
        )
        return {
            "card_narratives": fallback,
            "diagnostics": _build_completion_narrative_diagnostics(
                configured_provider=provider,
                returned_source="rules",
                status="rules",
                fallback_reason=fallback_reason,
                message=message,
            ),
        }

    fact_pack_json = json.dumps(build_completion_fact_pack(completion_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            raw_response = _request_completion_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"]),
                "diagnostics": _build_completion_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="google",
                    returned_source="google",
                    status="ai",
                    message="Completion narratives were generated by Google Gemini.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after Google completion narrative request failed: %s", error)
            if provider == "google":
                fallback_reason, message, detail = _classify_provider_error("google", error)
                return {
                    "card_narratives": fallback,
                    "diagnostics": _build_completion_narrative_diagnostics(
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
            return {
                "card_narratives": fallback,
                "diagnostics": _build_completion_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Completion narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }
        if provider == "auto" and not getattr(settings, "OPENAI_INSIGHTS_ENABLED", False):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_completion_narrative_diagnostics(
                    configured_provider=provider,
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="openai_not_enabled_for_auto_mode",
                    message="Completion narratives stayed on the rule-based engine because OpenAI narratives are not enabled in auto mode.",
                ),
            }
        try:
            raw_response = _request_completion_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by OpenAI Responses API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"]),
                "diagnostics": _build_completion_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="openai",
                    status="ai",
                    message="Completion narratives were generated by OpenAI.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after OpenAI completion narrative request failed: %s", error)
            fallback_reason, message, detail = _classify_provider_error("openai", error)
            return {
                "card_narratives": fallback,
                "diagnostics": _build_completion_narrative_diagnostics(
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
        "diagnostics": _build_completion_narrative_diagnostics(
            configured_provider=provider,
            returned_source="rules",
            status="fallback",
            fallback_reason="no_available_provider",
            message="Completion narratives are using the rule-based engine because no configured AI provider is available.",
        ),
    }

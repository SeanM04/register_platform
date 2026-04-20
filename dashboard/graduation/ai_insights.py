"""AI-assisted and rule-based narratives for the graduation dashboard."""

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
GOOGLE_GENERATE_CONTENT_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GRADUATION_CARD_KEYS = ("programme", "cohort", "faculty", "timing")
GRADUATION_CARD_SEVERITIES = {"stable", "medium", "high"}
GRADUATION_CARD_CONFIDENCES = {"low", "medium", "high"}
GRADUATION_CARD_SEVERITY_RANK = {"stable": 0, "medium": 1, "high": 2}
PROVIDER_LABELS = {
    "google": "Google Gemini",
    "openai": "OpenAI",
    "rules": "Rule-based engine",
    "auto": "Automatic provider selection",
}
GRADUATION_NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "object",
            "additionalProperties": False,
            "required": list(GRADUATION_CARD_KEYS),
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
                for card_key in GRADUATION_CARD_KEYS
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
        .replace("Master of Science", "MSc")
        .replace("Masters of Science", "MSc")
        .replace("Master of Commerce", "MCom")
        .replace("Masters of Commerce", "MCom")
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
                f"{_get_provider_label(provider_key)} timed out before returning graduation narratives.",
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
        f"{_get_provider_label(provider_key)} failed unexpectedly while generating graduation narratives.",
        detail,
    )


def _build_graduation_narrative_diagnostics(
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


def build_graduation_fact_pack(graduation_data):
    kpis = graduation_data.get("kpis", {})
    meta = graduation_data.get("meta", {})
    programme_rows = sorted(
        graduation_data.get("charts", {}).get("programme_graduation_rate", []),
        key=lambda row: float(row.get("graduation_rate", 0) or 0),
    )
    cohort_rows = sorted(
        graduation_data.get("charts", {}).get("cohort_graduation_rate", []),
        key=lambda row: (
            float(row.get("graduation_rate", 0) or 0),
            int(row.get("effective_cohort_sort_index", 0) or 0),
        ),
    )
    faculty_rows = sorted(
        graduation_data.get("charts", {}).get("faculty_graduation_rate", []),
        key=lambda row: float(row.get("graduation_rate", 0) or 0),
    )
    timing_rows = graduation_data.get("charts", {}).get("graduation_timing", [])
    strongest_programme = programme_rows[-1] if programme_rows else {}
    weakest_programme = programme_rows[0] if programme_rows else {}
    strongest_cohort = cohort_rows[-1] if cohort_rows else {}
    weakest_cohort = cohort_rows[0] if cohort_rows else {}
    strongest_faculty = faculty_rows[-1] if faculty_rows else {}
    weakest_faculty = faculty_rows[0] if faculty_rows else {}
    timing_map = {str(row.get("label", "")).strip(): int(row.get("count", 0) or 0) for row in timing_rows}
    total_timing = sum(timing_map.values())
    on_time_count = timing_map.get("On-time", 0)
    delayed_count = timing_map.get("Delayed", 0)

    return {
        "kpis": {
            "total_graduated_students": int(kpis.get("total_graduated_students", 0) or 0),
            "average_graduation_rate_pct": float(kpis.get("average_graduation_rate", 0) or 0),
            "on_time_graduation_rate_pct": float(kpis.get("on_time_graduation_rate", 0) or 0),
            "best_faculty_rate_pct": float(kpis.get("best_faculty_rate", 0) or 0),
        },
        "meta": {
            "has_graduates": bool(meta.get("has_graduates", False)),
            "snapshot_message": str(meta.get("snapshot_message", "")).strip(),
            "graduation_like_decision_count": int(meta.get("graduation_like_decision_count", 0) or 0),
            "students_one_step_from_target": int(meta.get("students_one_step_from_target", 0) or 0),
            "students_within_two_steps": int(meta.get("students_within_two_steps", 0) or 0),
        },
        "programme": {
            "strongest": strongest_programme,
            "weakest": weakest_programme,
            "rows": programme_rows[-6:],
        },
        "cohort": {
            "strongest": strongest_cohort,
            "weakest": weakest_cohort,
            "rows": cohort_rows[:6],
        },
        "faculty": {
            "strongest": strongest_faculty,
            "weakest": weakest_faculty,
            "rows": faculty_rows[-6:],
        },
        "timing": {
            "on_time_count": on_time_count,
            "delayed_count": delayed_count,
            "on_time_share_pct": round((on_time_count / total_timing) * 100, 1) if total_timing else 0.0,
            "delayed_share_pct": round((delayed_count / total_timing) * 100, 1) if total_timing else 0.0,
        },
    }


def _resolve_programme_severity(facts):
    weakest_rate = float(facts["programme"]["weakest"].get("graduation_rate", 0) or 0)
    if weakest_rate < 45:
        return "high"
    if weakest_rate < 65:
        return "medium"
    return "stable"


def _resolve_cohort_severity(facts):
    weakest_rate = float(facts["cohort"]["weakest"].get("graduation_rate", 0) or 0)
    if weakest_rate < 40:
        return "high"
    if weakest_rate < 60:
        return "medium"
    return "stable"


def _resolve_faculty_severity(facts):
    weakest_rate = float(facts["faculty"]["weakest"].get("graduation_rate", 0) or 0)
    if weakest_rate < 50:
        return "high"
    if weakest_rate < 70:
        return "medium"
    return "stable"


def _resolve_timing_severity(facts):
    on_time_rate = float(facts["kpis"].get("on_time_graduation_rate_pct", 0) or 0)
    if on_time_rate < 45:
        return "high"
    if on_time_rate < 70:
        return "medium"
    return "stable"


def build_rule_based_graduation_narratives(graduation_data):
    facts = build_graduation_fact_pack(graduation_data)
    if not facts["meta"]["has_graduates"]:
        snapshot_message = facts["meta"].get("snapshot_message") or "No visible students currently meet the documented graduation rule."
        readiness_students = facts["meta"].get("students_one_step_from_target", 0)
        within_two = facts["meta"].get("students_within_two_steps", 0)
        return {
            "source": "rules",
            "cards": {
                "programme": {
                    "insight": snapshot_message,
                    "action": (
                        f"Use the readiness charts first: {readiness_students} students are one step from target and {within_two} are within two steps."
                    ),
                    "severity": "medium",
                    "confidence": "low",
                },
                "cohort": {
                    "insight": "No visible cohort currently contains students who have already satisfied the documented graduation rule.",
                    "action": "Use readiness by cohort to see which effective intakes are closest to producing the first visible graduates.",
                    "severity": "medium",
                    "confidence": "low",
                },
                "faculty": {
                    "insight": "Faculty graduation rates are empty because the current snapshot has progression data but no confirmed graduates.",
                    "action": "Use the readiness charts and later-period data to see which faculties are nearest to crossing into graduation outcomes.",
                    "severity": "medium",
                    "confidence": "low",
                },
                "timing": {
                    "insight": "Timing analysis is empty because on-time versus delayed graduation only becomes measurable once visible graduates exist.",
                    "action": "Treat this as a pipeline view for now and monitor later-period records or award decisions before drawing timing conclusions.",
                    "severity": "stable",
                    "confidence": "low",
                },
            },
        }

    strongest_programme = facts["programme"]["strongest"]
    weakest_programme = facts["programme"]["weakest"]
    weakest_cohort = facts["cohort"]["weakest"]
    strongest_faculty = facts["faculty"]["strongest"]
    weakest_faculty = facts["faculty"]["weakest"]
    return {
        "source": "rules",
        "cards": {
            "programme": {
                "insight": (
                    f"{_short_programme_name(strongest_programme.get('programme_name'))} leads the visible programme set at "
                    f"{_format_pct(strongest_programme.get('graduation_rate'))}, while "
                    f"{_short_programme_name(str(weakest_programme.get('programme_name')))} trails at {_format_pct(weakest_programme.get('graduation_rate'))}."
                    if strongest_programme.get("programme_name") and weakest_programme.get("programme_name")
                    else "No programme graduation narrative is available for the current filters."
                ),
                "action": (
                    "Use the programme ranking to compare the lowest-graduating programmes before drilling into the student table."
                    if weakest_programme.get("programme_name")
                    else "Adjust the current filters to bring programme graduation patterns back into view."
                ),
                "severity": _resolve_programme_severity(facts),
                "confidence": "low",
            },
            "cohort": {
                "insight": (
                    f"{weakest_cohort.get('effective_cohort_label') or 'The weakest visible cohort'} is graduating at "
                    f"{_format_pct(weakest_cohort.get('graduation_rate'))} with "
                    f"{_format_count(weakest_cohort.get('graduated_count'))} graduates from "
                    f"{_format_count(weakest_cohort.get('enrolled_count'))} enrolled."
                    if weakest_cohort.get("effective_cohort_label")
                    else "No cohort graduation narrative is available for the current filters."
                ),
                "action": (
                    "Compare weaker cohort graduation bars against the stronger intakes to see where delays are building."
                    if weakest_cohort.get("effective_cohort_label")
                    else "Adjust the current filters to bring cohort graduation patterns back into view."
                ),
                "severity": _resolve_cohort_severity(facts),
                "confidence": "low",
            },
            "faculty": {
                "insight": (
                    f"{strongest_faculty.get('faculty') or 'The leading faculty'} currently leads at "
                    f"{_format_pct(strongest_faculty.get('graduation_rate'))}, while "
                    f"{weakest_faculty.get('faculty') or 'the weakest visible faculty'} sits at {_format_pct(weakest_faculty.get('graduation_rate'))}."
                    if strongest_faculty.get("faculty") and weakest_faculty.get("faculty")
                    else "No faculty graduation narrative is available for the current filters."
                ),
                "action": (
                    "Use the faculty chart to separate stronger graduation outcomes from units that may need progression support."
                    if strongest_faculty.get("faculty")
                    else "Adjust the current filters to bring faculty graduation patterns back into view."
                ),
                "severity": _resolve_faculty_severity(facts),
                "confidence": "low",
            },
            "timing": {
                "insight": (
                    f"{_format_pct(facts['kpis'].get('on_time_graduation_rate_pct'))} of visible graduates are on time, "
                    f"while {_format_pct(facts['timing'].get('delayed_share_pct'))} graduated after a cohort shift."
                ),
                "action": (
                    "Use the timing split to judge whether later cohort shifts are becoming a routine graduation path."
                ),
                "severity": _resolve_timing_severity(facts),
                "confidence": "low",
            },
        },
    }


def _normalize_ai_narrative_payload(payload, source, fallback_cards=None):
    cards = payload.get("cards", {})
    fallback_cards = fallback_cards or {}
    normalized_cards = {}
    for card_key in GRADUATION_CARD_KEYS:
        card = cards.get(card_key, {})
        insight = str(card.get("insight", "")).strip()
        action = str(card.get("action", "")).strip()
        if not insight or not action:
            raise ValueError(f"Missing narrative fields for {card_key}.")

        fallback_severity = str(fallback_cards.get(card_key, {}).get("severity", "stable")).strip().lower()
        severity = str(card.get("severity", fallback_severity)).strip().lower() or fallback_severity
        if severity not in GRADUATION_CARD_SEVERITIES:
            severity = fallback_severity if fallback_severity in GRADUATION_CARD_SEVERITIES else "stable"
        if (
            fallback_severity in GRADUATION_CARD_SEVERITIES
            and GRADUATION_CARD_SEVERITY_RANK[severity] < GRADUATION_CARD_SEVERITY_RANK[fallback_severity]
        ):
            severity = fallback_severity

        fallback_confidence = str(fallback_cards.get(card_key, {}).get("confidence", "medium")).strip().lower()
        confidence = str(card.get("confidence", fallback_confidence)).strip().lower() or fallback_confidence
        if confidence not in GRADUATION_CARD_CONFIDENCES:
            confidence = fallback_confidence if fallback_confidence in GRADUATION_CARD_CONFIDENCES else "medium"

        normalized_cards[card_key] = {
            "insight": insight,
            "action": action,
            "severity": severity,
            "confidence": confidence,
        }
    return {"source": source, "cards": normalized_cards}


def _build_narrative_prompt(fact_pack_json):
    return (
        "You generate concise dashboard narratives for a university graduation analytics page.\n"
        "Use only the supplied facts.\n"
        "Do not invent causes, trends, or interventions that are not directly supported by the facts.\n"
        "Write one 'insight' and one 'action' for each card.\n"
        "Keep each field to one sentence and under 28 words.\n"
        "If the facts show stable performance, the action should recommend monitoring or comparison, not alarm.\n\n"
        f"Facts:\n{fact_pack_json}"
    )


@lru_cache(maxsize=64)
def _request_graduation_openai_narratives(fact_pack_json):
    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "model": settings.OPENAI_INSIGHTS_MODEL,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 700,
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
                    "name": "graduation_card_narratives",
                    "schema": GRADUATION_NARRATIVE_SCHEMA,
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
def _request_graduation_google_narratives(fact_pack_json):
    prompt = _build_narrative_prompt(fact_pack_json)
    payload = {
        "systemInstruction": {
            "parts": [{"text": "Return only structured dashboard narrative fields that match the schema."}]
        },
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 700,
            "responseMimeType": "application/json",
            "responseJsonSchema": GRADUATION_NARRATIVE_SCHEMA,
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


def get_graduation_card_narratives_result(graduation_data):
    fallback = build_rule_based_graduation_narratives(graduation_data)
    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        fallback_reason = "provider_rules_configured" if provider == "rules" else "ai_insights_disabled"
        message = (
            "Graduation narratives are using the rule-based engine because AI provider mode is set to rules."
            if provider == "rules"
            else "Graduation narratives are using the rule-based engine because AI insights are disabled."
        )
        return {
            "card_narratives": fallback,
            "diagnostics": _build_graduation_narrative_diagnostics(
                configured_provider=provider,
                returned_source="rules",
                status="rules",
                fallback_reason=fallback_reason,
                message=message,
            ),
        }

    fact_pack_json = json.dumps(build_graduation_fact_pack(graduation_data), sort_keys=True)

    if provider in {"auto", "google"} and getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            raw_response = _request_graduation_google_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_google_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by Gemini API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "google", fallback["cards"]),
                "diagnostics": _build_graduation_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="google",
                    returned_source="google",
                    status="ai",
                    message="Graduation narratives were generated by Google Gemini.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after Google graduation narrative request failed: %s", error)
            if provider == "google":
                fallback_reason, message, detail = _classify_provider_error("google", error)
                return {
                    "card_narratives": fallback,
                    "diagnostics": _build_graduation_narrative_diagnostics(
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
                "diagnostics": _build_graduation_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="missing_openai_api_key",
                    message="Graduation narratives are using the rule-based engine because the OpenAI API key is missing.",
                ),
            }
        if provider == "auto" and not getattr(settings, "OPENAI_INSIGHTS_ENABLED", False):
            return {
                "card_narratives": fallback,
                "diagnostics": _build_graduation_narrative_diagnostics(
                    configured_provider=provider,
                    returned_source="rules",
                    status="fallback",
                    fallback_reason="openai_not_enabled_for_auto_mode",
                    message="Graduation narratives stayed on the rule-based engine because OpenAI narratives are not enabled in auto mode.",
                ),
            }
        try:
            raw_response = _request_graduation_openai_narratives(fact_pack_json)
            response_payload = json.loads(raw_response)
            response_text = _extract_response_text(response_payload)
            if not response_text:
                raise ValueError("No output text returned by OpenAI Responses API.")
            return {
                "card_narratives": _normalize_ai_narrative_payload(json.loads(response_text), "openai", fallback["cards"]),
                "diagnostics": _build_graduation_narrative_diagnostics(
                    configured_provider=provider,
                    provider_attempted="openai",
                    returned_source="openai",
                    status="ai",
                    message="Graduation narratives were generated by OpenAI.",
                ),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError) as error:
            logger.warning("Falling back after OpenAI graduation narrative request failed: %s", error)
            fallback_reason, message, detail = _classify_provider_error("openai", error)
            return {
                "card_narratives": fallback,
                "diagnostics": _build_graduation_narrative_diagnostics(
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
        "diagnostics": _build_graduation_narrative_diagnostics(
            configured_provider=provider,
            returned_source="rules",
            status="fallback",
            fallback_reason="no_available_provider",
            message="Graduation narratives are using the rule-based engine because no configured AI provider is available.",
        ),
    }

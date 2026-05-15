"""Platform chatbot service for the UniStudio web assistant."""

from __future__ import annotations

import json
import logging
import re
import statistics
import threading
import time
import urllib.error
import urllib.request
from typing import Iterable

from django.conf import settings
from django.db.models import Avg, Count, Q

from dashboard.models import AcademicPeriod, Course, CourseResult, Faculty, Programme, Registration, Student
from dashboard.risk.constants import HIGH_RISK_DECISIONS, RISK_BAND_DEFINITIONS, RISK_DRIVER_LABELS
from services.completion_rules import (
    PASS_MARK as _CR_PASS_MARK,
    get_zero_completion_decision,
    student_completion_percentage,
)

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GOOGLE_GENERATE_CONTENT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# ---------------------------------------------------------------------------
# Intent detection — mirrors Layer 2 (IntentDetector) of the original prototype
# ---------------------------------------------------------------------------
INTENT_PROMPT = (
    "Classify the user message for UniStudio Bot at MSUAS university (Zimbabwe).\n\n"
    "Choose exactly one intent:\n"
    "- student_lookup   : asking about a specific student by registration number\n"
    "- at_risk          : failing, struggling, or at-risk students\n"
    "- comparison       : comparing programmes, faculties, courses, or periods\n"
    "- calculation      : completion %, GPA, risk score, or graduation rate explained\n"
    "- demographic      : gender breakdown, year distribution, origin stats\n"
    "- decision_analysis: academic decisions (Proceed, Retake, Repeat, Discontinue)\n"
    "- data_query       : pass rates, statistics, mark distributions, totals, top/best performing students, rankings\n"
    "- admissions       : applying to MSUAS, entry requirements, how to enrol\n"
    "- general_info     : location, contacts, directions, portals, fees, calendar\n"
    "- greeting         : hello, hi, thanks, greetings\n"
    "- out_of_scope     : completely unrelated to MSUAS or education\n\n"
    "Extract entities if present:\n"
    "- regnum: student registration number (e.g. M22ABC, M23XYZ)\n"
    "- programme_codes: list of codes mentioned (e.g. ACCT, BMAN, INSY, CHEP)\n"
    "- period: academic period mentioned (e.g. August 2025, Semester 1)\n"
    "- faculty: faculty name mentioned\n"
    "- risk_band: low / moderate / high / critical\n\n"
    "Respond ONLY in JSON (no markdown, no extra text):\n"
    '{"intent":"...","entities":{"regnum":null,"programme_codes":[],'
    '"period":null,"faculty":null,"risk_band":null}}'
)

# Intents whose rule-based replies are safe to cache (no personal student data)
CACHEABLE_INTENTS = frozenset({
    "data_query", "admissions", "general_info", "comparison",
    "demographic", "decision_analysis", "calculation",
})

# Core academic constants — kept in sync with completion_rules.py and risk/constants.py
PASS_MARK = _CR_PASS_MARK          # 50.0
MAX_HISTORY_MESSAGES = 8
MAX_PROGRAMME_ROWS = 8
MAX_FACULTY_ROWS = 5
MAX_DECISION_ROWS = 6
MAX_AT_RISK_ROWS = 10
MAX_COURSE_ROWS = 8
MAX_MESSAGE_LENGTH = 1200

# Degree classification scale (1st Class Honours → Fail)
GRADING_SCALE = (
    ("1st Class Honours", 75, 100),
    ("2.1 Upper Second",  65,  74),
    ("2.2 Lower Second",  60,  64),
    ("3rd Class",         50,  59),
    ("Fail",               0,  49),
)

# Programme target periods — mirrors graduation_services._target_period_from_programme()
PROGRAMME_DURATIONS = {
    "masters":     4,   # Year 2 Semester 2
    "engineering": 10,  # Year 5 Semester 2
    "default":     8,   # Year 4 Semester 2
}

REGNUM_PATTERN = re.compile(r"\b[a-z]\d[a-z0-9]{3,}\b", re.IGNORECASE)
COURSE_CODE_PATTERN = re.compile(r"\b[a-z]{3,}\d{3,}\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Tool registry — registered with OpenAI / Google for function calling.
# These 8 tools replace the 20-handler keyword dispatch; the AI decides which
# ones to call based on the user's question and conversation context.
# Stored in OpenAI JSON-Schema format; converted to Google format dynamically.
# ---------------------------------------------------------------------------
CHATBOT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_top_students",
            "description": (
                "Return the top-N students ranked by average mark. Use for: "
                "'top 5 students in year 2', 'best performer', 'who has the highest marks', "
                "'number one student in INSY', 'who is leading academically'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "How many students to return (default 5, max 20).", "minimum": 1, "maximum": 20},
                    "year_level": {"type": "integer", "description": "Academic year level 1–5 to filter by. Omit for all years.", "minimum": 1, "maximum": 5},
                    "programme_code": {"type": "string", "description": "Programme code filter, e.g. 'INSY', 'ACCT'."},
                    "faculty": {"type": "string", "description": "Faculty name filter."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_student_profile",
            "description": (
                "Return full academic profile for a specific student: marks, risk score, "
                "completion history, decisions, graduation rate. Use when a registration number "
                "is mentioned (e.g. 'M213TX') or the user says 'yes' / 'show me more' after "
                "the bot offered a profile in the previous turn."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "registration_number": {"type": "string", "description": "Student registration number, e.g. 'M213TX'."},
                },
                "required": ["registration_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_at_risk_students",
            "description": (
                "Return students flagged for academic risk: multiple failures, adverse decisions, "
                "or carrying courses. Use for: 'struggling students', 'at risk', 'failing', "
                "'watchlist', 'who needs help', 'discontinue students'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "risk_band": {"type": "string", "enum": ["moderate", "high", "critical"], "description": "Filter by band. Omit for all risk levels."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_programme_statistics",
            "description": (
                "Return pass rates, average marks, student counts, and gender breakdown for programmes. "
                "Use for: 'how is INSY performing', 'pass rate for accounting', 'compare ACCT and BMAN'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "programme_codes": {"type": "array", "items": {"type": "string"}, "description": "Programme codes to query, e.g. ['INSY', 'ACCT']. Empty means all in scope."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_faculty_statistics",
            "description": (
                "Return student counts, pass rates, and gender breakdown aggregated by faculty. "
                "Use for: 'how is Engineering faculty performing', 'which faculty has the best pass rate'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "faculty_name": {"type": "string", "description": "Faculty name to query. Omit for all faculties in scope."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_demographic_breakdown",
            "description": (
                "Return gender breakdown and academic year distribution statistics. "
                "Use for: 'gender stats', 'male vs female', 'year distribution', 'how many year 1 students', "
                "'demographic breakdown'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year_level": {"type": "integer", "description": "Filter by academic year level 1–5. Omit for all years.", "minimum": 1, "maximum": 5},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_course_difficulty_ranking",
            "description": (
                "Return courses ranked hardest to easiest by average student mark. "
                "Use for: 'hardest course', 'easiest subject', 'which course has lowest pass rate', "
                "'course difficulty'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_period_performance",
            "description": (
                "Return performance statistics for a specific academic period or semester. "
                "Use when a period name, month, or semester number is mentioned, "
                "e.g. 'August 2024 performance', 'how did Semester 1 2025 go'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period_name": {"type": "string", "description": "Period name e.g. 'August 2024', 'Semester 1 2025'."},
                },
                "required": ["period_name"],
            },
        },
    },
]

# Short words that strongly signal a follow-up reply rather than a new topic.
_FOLLOWUP_TOKENS = frozenset({
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright",
    "no", "nope", "nah", "please", "go", "ahead", "show", "tell",
    "more", "continue", "which", "those", "them", "that", "these",
    "it", "how", "break", "drill", "elaborate", "explain", "details",
    "and", "also", "what", "about", "further", "deeper",
})

# Expanded safety patterns — includes jailbreak and instruction-override attacks
SENSITIVE_PATTERNS = (
    r"\b(api[_ -]?key|secret|token|credential|password)\b",
    r"\b(hack|exploit|bypass|inject|steal|jailbreak)\b",
    r"\bignore (previous|all|your) instructions?\b",
    r"\bact as (a different|another|an? (unfiltered|uncensored))\b",
)

PROVIDER_LABELS = {
    "google": "Google Gemini",
    "openai": "OpenAI",
    "rules": "Guidance",
}

# ---------------------------------------------------------------------------
# In-process session context cache — persists active data across follow-up turns
# Keyed by Django session key; each entry holds the last tool results so "yes"
# responses can re-use the previous turn's fetched data without a full re-query.
# ---------------------------------------------------------------------------
_SESSION_CONTEXT: dict[str, dict] = {}
_SESSION_LOCK = threading.Lock()
_SESSION_TTL = 7200  # 2 hours


def _get_session_ctx(session_id: str | None) -> dict:
    if not session_id:
        return {}
    with _SESSION_LOCK:
        entry = _SESSION_CONTEXT.get(session_id)
        if entry and (time.time() - entry["ts"]) < _SESSION_TTL:
            return entry["data"]
        if entry:
            del _SESSION_CONTEXT[session_id]
    return {}


def _store_session_ctx(session_id: str | None, data: dict) -> None:
    if not session_id:
        return
    with _SESSION_LOCK:
        _SESSION_CONTEXT[session_id] = {"ts": time.time(), "data": data}
        now = time.time()
        expired = [k for k, v in _SESSION_CONTEXT.items() if now - v["ts"] > _SESSION_TTL]
        for k in expired:
            del _SESSION_CONTEXT[k]

UNIVERSITY_FACTS = {
    "name": "Manicaland State University of Applied Sciences (MSUAS)",
    "location": "Stair Guthrie Road, P Bag 7001, Fernhill, Mutare, Manicaland, Zimbabwe",
    "phone": "+263 2063456 | +263 8677004392",
    "email": "pr@msuas.ac.zw",
    "website": "https://msuas.ac.zw",
    "applications": "https://admissions.msuas.ac.zw",
    "student_portal": "https://elearning.msuas.ac.zw",
    "my_msuas_portal": "http://my.msuas.ac.zw/kunda/login",
    "library": "https://library.msuas.ac.zw",
    "teaching_timetable": "https://teachingtimetable.msuas.ac.zw",
    "certificate_verification": "https://msuas.ac.zw/certificate-verification/",
    "founded": "2016 (celebrating its 10th anniversary in 2026)",
    "directions": (
        "MSUAS is in Fernhill, Mutare, eastern Zimbabwe near the Mozambique border. "
        "Mutare is approximately 263 km from Harare (about 3.5 hours by road via the Mutare-Harare highway). "
        "From central Mutare head towards Fernhill — the campus is on Stair Guthrie Road. "
        "Nearest bus terminus: Sakubva bus terminus in central Mutare."
    ),
}

ADMISSIONS_SUMMARY = (
    "Minimum entry: 5 O-Level passes including English Language at grade C or better, "
    "plus programme-specific A-Level subjects or relevant diplomas. "
    "Apply at https://admissions.msuas.ac.zw — August 2026 intake currently in progress. "
    "Requirements by faculty: Engineering — Mathematics and Physics at A-Level; "
    "Business/Commerce — Commerce or Mathematics at A-Level; "
    "Applied Sciences/IT — Mathematics and Science at A-Level; "
    "Agricultural Sciences — Biology or Agriculture at A-Level; "
    "Social Sciences — relevant Arts/Science combination at A-Level. "
    "Postgraduate: a relevant undergraduate degree with at least a 2.1 (Lower Second) classification."
)

STUDENT_SERVICES_SUMMARY = (
    "On-campus services: Health Services, Disability Unit, Sports Services, Accommodation/Residency. "
    "Student Advisory Office available for academic and personal support. "
    "Certificate and transcript verification: https://msuas.ac.zw/certificate-verification/. "
    "New 2026 programmes: BSc Crop Science, BSc Horticulture, BSc Agricultural Engineering, "
    "BSc Human Resource Management, BSc Organisational Psychology, MSc Agroecology, "
    "MSc Tourism and Hospitality, BEng Metallurgy, BEng Mining and Mineral Processing. "
    "Short courses: Sales & Marketing, Stress Management, Drug & Substance Management."
)

OUT_OF_SCOPE_REPLY = (
    "I am UniStudio Bot, specialising in MSUAS academic records, student performance, "
    "and university information. I can help with pass rates, student data, programme "
    "statistics, admissions, and anything related to MSUAS. What would you like to know?"
)

GREETING_REPLY = (
    "Hello! I am UniStudio Bot, the academic analytics assistant for the UniStudio "
    "registrar platform at MSUAS. I can help you with student profiles, programme "
    "pass rates, at-risk students, completion rules, admissions, and university "
    "information. What would you like to know?"
)

COMPLETION_RULES_SUMMARY = (
    "Completion uses a pass mark of 50. If a student has any zero-completion decision for the semester "
    "(Repeat, Deferred, Discontinue, Expelled, Results Nullified, Results Suppressed, "
    "Suspended for 2 Semesters), completion is 0%. "
    "If there is no zero-completion decision but the student fails 4 or more courses, completion is also 0%. "
    "Otherwise completion = (passed courses / total courses) x 100. "
    "Students with a 'Proceed Carrying' decision carry a failed course into the next semester — "
    "their completion is calculated normally but their carrying count is incremented."
)

GRADUATION_RULES_SUMMARY = (
    "Graduation stage is determined by programme family: masters programmes end at Year 2 Semester 2, "
    "engineering programmes at Year 5 Semester 2, and most other programmes at Year 4 Semester 2. "
    "On-time graduation means the effective cohort stayed equal to the original cohort."
)

RISK_BANDS_SUMMARY = (
    "Risk bands are determined by a scored assessment: "
    "Low (score 0-1): normal progression, minor or no concerns; "
    "Moderate (score 2-3): one academic setback or borderline average mark; "
    "High (score 4-5): Repeat/Retake decision combined with below-average marks; "
    "Critical (score 6+): severe academic actions (Discontinue, Expelled, Dismissed) or multiple failed semesters. "
    "Drivers include: severe_academic_action, academic_setback, supplementary_assessment, "
    "carrying_courses, below_pass_average, borderline_average, multiple_failed_semesters."
)


# =============================================================================
# COMPUTATION HELPERS — aligned with each dashboard page's service
# =============================================================================

def _classify_mark(mark: float | None) -> str:
    """Return the degree classification for a mark.
    Mirrors the GRADING_SCALE from unistudio_chatbot.py and the academic rules
    displayed on every page of the platform.
    """
    if mark is None:
        return "No marks recorded"
    for label, low, high in GRADING_SCALE:
        if low <= mark <= high:
            return label
    return "Unknown"


def _target_period(programme_name: str) -> int:
    """Return the expected number of semesters to graduation.
    Mirrors graduation_services._target_period_from_programme().
    """
    name_lower = str(programme_name or "").lower()
    if "master" in name_lower or "msc" in name_lower:
        return PROGRAMME_DURATIONS["masters"]
    if "engineering" in name_lower or "beng" in name_lower:
        return PROGRAMME_DURATIONS["engineering"]
    return PROGRAMME_DURATIONS["default"]


def _graduation_rate(completion_values: list[float], target_period: int) -> float:
    """Average completion across all required periods (pads with 0.0 if short).
    Mirrors graduation_services graduation rate calculation.
    """
    if not completion_values or target_period < 1:
        return 0.0
    padded = list(completion_values) + [0.0] * max(0, target_period - len(completion_values))
    return round(sum(padded[:target_period]) / target_period, 1)


def _risk_score_for_chat(
    avg_mark: float | None,
    failed_count: int,
    carrying: int,
    decision: str,
) -> dict:
    """Score a student's academic risk.
    Algorithm matches dashboard/risk/services.py assess_student_risk() exactly,
    using the same thresholds, drivers, and band definitions from risk/constants.py.

    Returns:
        {"score": int, "band": str, "drivers": list[str], "driver_labels": list[str]}
    """
    score = 0
    drivers: list[str] = []

    # Average mark assessment
    if avg_mark is not None:
        if avg_mark < PASS_MARK:
            score += 3
            drivers.append("average_below_50")
        elif avg_mark < 60:
            score += 1
            drivers.append("average_below_60")

    # Failed course count
    if failed_count >= 3:
        score += 3
        drivers.append("failed_3_plus")
    elif failed_count == 2:
        score += 2
        drivers.append("failed_2")
    elif failed_count == 1:
        score += 1
        drivers.append("failed_1")

    # Carrying courses
    if carrying >= 2:
        score += 2
        drivers.append("carrying_multi")
    elif carrying == 1:
        score += 1
        drivers.append("carrying_1")

    # Adverse decision — exact match, mirrors assess_student_risk() in risk/services.py
    decision_key = str(decision or "").strip().lower()
    if decision_key in HIGH_RISK_DECISIONS:
        score += 2
        drivers.append("decision_alert")

    # Band classification — matches RISK_BAND_DEFINITIONS in risk/constants.py
    band = "low"
    for band_def in RISK_BAND_DEFINITIONS:
        min_s = band_def["min_score"]
        max_s = band_def["max_score"]
        if max_s is None:
            if score >= min_s:
                band = band_def["key"]
                break
        elif min_s <= score <= max_s:
            band = band_def["key"]
            break

    return {
        "score": score,
        "band": band,
        "drivers": drivers,
        "driver_labels": [RISK_DRIVER_LABELS.get(d, d) for d in drivers],
    }


def _format_period_label(period_name: str) -> str:
    if not period_name:
        return ""

    year_match = re.search(r"(20\d{2})", period_name)
    if year_match:
        text = period_name.replace(year_match.group(0), "").strip()
    else:
        text = period_name
    return re.sub(r"\s+", " ", text.replace("-", " - ")).strip(" -").title()


def _normalize_filters(filters: dict | None) -> dict:
    filters = filters or {}
    return {
        "year": str(filters.get("year", "") or "").strip(),
        "period": str(filters.get("period", "") or "").strip(),
        "faculty": str(filters.get("faculty", "") or "").strip(),
    }


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _truncate(value: str, limit: int = MAX_MESSAGE_LENGTH) -> str:
    value = str(value or "").strip()
    return value[:limit]


def _extract_response_text(response_payload):
    # Chat Completions format (used by the multi-turn request function)
    choices = response_payload.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
        if content:
            return str(content).strip()
    # Responses API format (legacy fallback)
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    for block in response_payload.get("output", []):
        for content in block.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return str(content["text"]).strip()
    return ""


def _extract_google_response_text(response_payload):
    for candidate in response_payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if part.get("text"):
                return str(part["text"]).strip()
    return ""


def get_chatbot_provider_status() -> dict:
    # Prefer the DB-stored selection (set via System Management → AI Insights)
    # so the chatbot honours the same provider the admin chose for narratives.
    try:
        from dashboard.models import PlatformSetting
        _db_provider = PlatformSetting.get_value("ai_provider", "").strip().lower()
    except Exception:  # noqa: BLE001
        _db_provider = ""
    provider = _db_provider or getattr(settings, "CHATBOT_PROVIDER", "auto").strip().lower()
    enabled = bool(getattr(settings, "CHATBOT_ENABLED", True))
    google_ready = provider in {"auto", "google"} and bool(getattr(settings, "GOOGLE_API_KEY", ""))
    openai_ready = provider in {"auto", "openai"} and bool(getattr(settings, "OPENAI_API_KEY", ""))
    return {
        "enabled": enabled,
        "provider": provider,
        "google_ready": google_ready,
        "openai_ready": openai_ready,
        "ai_available": google_ready or openai_ready,
    }


def _apply_scope_filters(queryset, filters: dict):
    selected_year = filters.get("year", "")
    selected_period = filters.get("period", "")
    selected_faculty = filters.get("faculty", "")

    if selected_year:
        queryset = queryset.filter(period__name__icontains=selected_year)

    if selected_period:
        matching_period_names = [
            period.name
            for period in AcademicPeriod.objects.all()
            if _format_period_label(period.name) == selected_period
        ]
        if matching_period_names:
            queryset = queryset.filter(period__name__in=matching_period_names)

    if selected_faculty:
        queryset = queryset.filter(programme__department__faculty__name=selected_faculty)

    return queryset


def _base_registrations(filters: dict):
    queryset = (
        Registration.objects.select_related(
            "student",
            "programme__department__faculty",
            "period",
        )
        .prefetch_related("course_results__course")
        .order_by("student__surname", "student__first_names", "period__external_id")
    )
    return _apply_scope_filters(queryset, filters)


def _safe_round(value, digits=1):
    return round(float(value), digits) if value is not None else None


def _format_pct(value):
    if value is None:
        return "N/A"
    return f"{round(float(value), 1)}%"


def _summarize_scope(filters: dict, registrations, results):
    registration_list = list(registrations)
    result_count = results.count()
    total_students = len({registration.student_id for registration in registration_list})
    avg_mark = results.aggregate(value=Avg("mark"))["value"]
    _all_marks = list(results.values_list("mark", flat=True))
    median_mark = _safe_round(statistics.median(_all_marks)) if _all_marks else None
    pass_count = results.filter(mark__gte=PASS_MARK).count()
    pass_rate = (pass_count / result_count * 100) if result_count else None

    failed_ids = set(
        results.filter(mark__lt=PASS_MARK)
        .values("registration__student_id")
        .annotate(fail_count=Count("id"))
        .filter(fail_count__gte=2)
        .values_list("registration__student_id", flat=True)
    )
    carrying_ids = set(
        registration.student_id
        for registration in registration_list
        if int(registration.carrying or 0) > 0
    )
    # Exact-match against HIGH_RISK_DECISIONS — mirrors assess_student_risk() in risk/services.py
    adverse_ids = set(
        registration.student_id
        for registration in registration_list
        if str(registration.decision or "").strip().lower() in HIGH_RISK_DECISIONS
    )
    watchlist_count = len(failed_ids | carrying_ids | adverse_ids)

    faculty_rows = list(
        _apply_scope_filters(
            Registration.objects.select_related("programme__department__faculty"),
            filters,
        )
        .values("programme__department__faculty__name")
        .annotate(
            students=Count("student_id", distinct=True),
            registrations=Count("id"),
        )
        .order_by("-students", "programme__department__faculty__name")[:MAX_FACULTY_ROWS]
    )

    programme_rows = list(
        results.values("registration__programme__code", "registration__programme__name")
        .annotate(
            students=Count("registration__student_id", distinct=True),
            registrations=Count("registration_id", distinct=True),
            avg_mark=Avg("mark"),
            passed=Count("id", filter=Q(mark__gte=PASS_MARK)),
            total_results=Count("id"),
        )
        .order_by("-students", "registration__programme__name")[:MAX_PROGRAMME_ROWS]
    )

    all_decision_rows = list(
        _apply_scope_filters(Registration.objects.all(), filters)
        .exclude(decision__isnull=True)
        .exclude(decision__exact="")
        .values("decision")
        .annotate(count=Count("id"))
        .order_by("-count", "decision")
    )
    _total_decisions = sum(r["count"] for r in all_decision_rows)
    proceeding_count = sum(
        r["count"] for r in all_decision_rows
        if "proceed" in str(r["decision"]).lower()
    )
    decision_rows = all_decision_rows[:MAX_DECISION_ROWS]

    gender_rows = list(
        _apply_scope_filters(Registration.objects.all(), filters)
        .values("student__gender")
        .annotate(count=Count("student_id", distinct=True))
        .order_by("-count")
    )
    _total_gendered = sum(row["count"] for row in gender_rows)
    gender_breakdown = {
        (row["student__gender"] or "Unspecified").title(): {
            "count": row["count"],
            "pct": round(row["count"] / _total_gendered * 100, 1) if _total_gendered else 0,
        }
        for row in gender_rows
    }

    return {
        "filters": filters,
        "total_students": total_students,
        "total_registrations": len(registration_list),
        "total_results": result_count,
        "average_mark": _safe_round(avg_mark),
        "median_mark": median_mark,
        "pass_rate": _safe_round(pass_rate),
        "watchlist_count": watchlist_count,
        "multi_fail_count": len(failed_ids),
        "carrying_count": len(carrying_ids),
        "adverse_decision_count": len(adverse_ids),
        "proceeding_count": proceeding_count,
        "proceeding_pct": _safe_round(proceeding_count / _total_decisions * 100) if _total_decisions else None,
        "at_risk_pct": _safe_round(len(adverse_ids) / total_students * 100) if total_students else None,
        "gender_breakdown": gender_breakdown,
        "top_faculties": [
            {
                "faculty": row["programme__department__faculty__name"] or "Unassigned",
                "students": row["students"],
                "registrations": row["registrations"],
            }
            for row in faculty_rows
        ],
        "top_programmes": [
            {
                "code": row["registration__programme__code"],
                "name": row["registration__programme__name"],
                "students": row["students"],
                "registrations": row["registrations"],
                "average_mark": _safe_round(row["avg_mark"]),
                "pass_rate": _safe_round((row["passed"] / row["total_results"] * 100) if row["total_results"] else None),
            }
            for row in programme_rows
        ],
        "top_decisions": [
            {
                "decision": row["decision"].title(),
                "count": row["count"],
            }
            for row in decision_rows
        ],
    }


def _find_student_targets(message: str):
    matches = REGNUM_PATTERN.findall(message or "")
    return [match.upper() for match in matches[:2]]


def _match_entities(message: str, model, name_field: str, code_field: str | None = None, limit: int = 3):
    normalized_message = _normalize_text(message)
    matches = []
    for row in model.objects.all()[:500]:
        candidates = [_normalize_text(getattr(row, name_field, ""))]
        if code_field:
            candidates.append(_normalize_text(getattr(row, code_field, "")))
        if any(candidate and candidate in normalized_message for candidate in candidates):
            matches.append(row)
        if len(matches) >= limit:
            break
    return matches


def _build_student_context(registration_number: str):
    student = (
        Student.objects.filter(registration_number__iexact=registration_number)
        .prefetch_related("registrations__programme__department__faculty", "registrations__period", "registrations__course_results__course")
        .first()
    )
    if not student:
        return None

    registrations = sorted(
        student.registrations.all(),
        key=lambda row: (row.period.external_id, row.id),
        reverse=True,
    )
    latest_registration = registrations[0] if registrations else None
    latest_results = [
        {
            "course_code": result.course.code if result.course else "",
            "course_name": result.course.name if result.course else "",
            "mark": _safe_round(result.mark, 0),
        }
        for result in (latest_registration.course_results.all() if latest_registration else [])[:8]
    ]
    all_marks = [
        float(result.mark)
        for registration in registrations
        for result in registration.course_results.all()
        if result.mark is not None
    ]
    avg_mark = _safe_round(sum(all_marks) / len(all_marks)) if all_marks else None
    latest_faculty = (
        latest_registration.programme.department.faculty.name
        if latest_registration and latest_registration.programme and latest_registration.programme.department
        else "Unassigned"
    )

    # Per-period completion — calls student_completion_percentage() from completion_rules.py
    period_completions = []
    for reg in reversed(registrations):  # chronological order
        marks = [float(r.mark) for r in reg.course_results.all() if r.mark is not None]
        decision_str = str(reg.decision or "")
        completion = student_completion_percentage(marks, decision_str)
        failed_count = sum(1 for m in marks if m < PASS_MARK)
        # Build zero_reason — mirrors prototype's _calculate_completion working field
        zero_reason = None
        if completion == 0.0 and marks:
            zcd = get_zero_completion_decision(decision_str)
            if zcd is not None:
                zero_reason = f"zero-completion decision: {decision_str} ({zcd.label})"
            elif failed_count >= 4:
                zero_reason = f"{failed_count} courses failed (threshold is 4)"
        period_completions.append({
            "period": reg.period.name if reg.period else "",
            "completion": completion,
            "passed": sum(1 for m in marks if m >= PASS_MARK),
            "total": len(marks),
            "failed": failed_count,
            "decision": decision_str,
            "zero_reason": zero_reason,
            "working": (
                f"({sum(1 for m in marks if m >= PASS_MARK)}/{len(marks)}) x 100 = {completion}%"
                if completion > 0 else f"0% — {zero_reason or 'no marks'}"
            ),
        })

    # Risk score for the latest registration — mirrors assess_student_risk() in risk/services.py
    latest_failed = sum(
        1 for result in (latest_registration.course_results.all() if latest_registration else [])
        if result.mark is not None and float(result.mark) < PASS_MARK
    )
    latest_carrying = int(latest_registration.carrying or 0) if latest_registration else 0
    latest_decision_raw = str(latest_registration.decision or "").strip().lower() if latest_registration else ""
    risk = _risk_score_for_chat(avg_mark, latest_failed, latest_carrying, latest_decision_raw)

    # Graduation rate — uses _graduation_rate() aligned with graduation_services.py
    programme_name = latest_registration.programme.name if latest_registration else ""
    target = _target_period(programme_name)
    grad_rate = _graduation_rate([row["completion"] for row in period_completions], target)

    return {
        "registration_number": student.registration_number,
        "name": student.full_name,
        "gender": student.gender or "Unspecified",
        "programme": programme_name,
        "faculty": latest_faculty,
        "latest_period": latest_registration.period.name if latest_registration else "",
        "latest_decision": str(latest_registration.decision or "").title() if latest_registration else "",
        "carrying": latest_carrying,
        "average_mark": avg_mark,
        "classification": _classify_mark(avg_mark),
        "risk": risk,
        "graduation_rate": grad_rate,
        "period_completions": period_completions[-4:],  # last 4 periods
        "recent_courses": latest_results,
    }


def _build_programme_context(programmes: Iterable[Programme], filters: dict):
    rows = []
    for programme in programmes:
        scoped_registrations = _apply_scope_filters(
            Registration.objects.filter(programme=programme),
            filters,
        )
        scoped_results = CourseResult.objects.filter(registration__in=scoped_registrations).exclude(mark__isnull=True)
        total_results = scoped_results.count()
        passed = scoped_results.filter(mark__gte=PASS_MARK).count()
        gender_rows = list(
            scoped_registrations.values("student__gender")
            .annotate(count=Count("student_id", distinct=True))
            .order_by("-count")
        )
        _total_gendered = sum(r["count"] for r in gender_rows)
        gender_breakdown = {
            (r["student__gender"] or "Unspecified").title(): {
                "count": r["count"],
                "pct": round(r["count"] / _total_gendered * 100, 1) if _total_gendered else 0,
            }
            for r in gender_rows
        }
        rows.append(
            {
                "code": programme.code,
                "name": programme.name,
                "faculty": programme.department.faculty.name if programme.department else "Unassigned",
                "students": scoped_registrations.values("student_id").distinct().count(),
                "registrations": scoped_registrations.count(),
                "average_mark": _safe_round(scoped_results.aggregate(value=Avg("mark"))["value"]),
                "pass_rate": _safe_round((passed / total_results * 100) if total_results else None),
                "fail_rate": _safe_round(((total_results - passed) / total_results * 100) if total_results else None),
                "carrying_count": scoped_registrations.filter(carrying__gt=0).count(),
                "gender_breakdown": gender_breakdown,
            }
        )
    return rows


def _build_faculty_context(faculties: Iterable[Faculty], filters: dict):
    rows = []
    for faculty in faculties:
        scoped_registrations = _apply_scope_filters(
            Registration.objects.filter(programme__department__faculty=faculty),
            filters,
        )
        scoped_results = CourseResult.objects.filter(registration__in=scoped_registrations).exclude(mark__isnull=True)
        total_results = scoped_results.count()
        passed = scoped_results.filter(mark__gte=PASS_MARK).count()
        gender_rows = list(
            scoped_registrations.values("student__gender")
            .annotate(count=Count("student_id", distinct=True))
            .order_by("-count")
        )
        _total_gendered = sum(r["count"] for r in gender_rows)
        gender_breakdown = {
            (r["student__gender"] or "Unspecified").title(): {
                "count": r["count"],
                "pct": round(r["count"] / _total_gendered * 100, 1) if _total_gendered else 0,
            }
            for r in gender_rows
        }
        rows.append(
            {
                "faculty": faculty.name,
                "students": scoped_registrations.values("student_id").distinct().count(),
                "registrations": scoped_registrations.count(),
                "average_mark": _safe_round(scoped_results.aggregate(value=Avg("mark"))["value"]),
                "pass_rate": _safe_round((passed / total_results * 100) if total_results else None),
                "gender_breakdown": gender_breakdown,
            }
        )
    return rows


def _build_course_context(message: str, filters: dict):
    code_match = COURSE_CODE_PATTERN.search(message or "")
    if not code_match:
        return None
    course_code = code_match.group(0).upper()
    course = Course.objects.filter(code__iexact=course_code).first()
    if not course:
        return None
    scoped_registrations = _apply_scope_filters(Registration.objects.all(), filters)
    scoped_results = CourseResult.objects.filter(
        registration__in=scoped_registrations,
        course=course,
    ).exclude(mark__isnull=True)
    total_results = scoped_results.count()
    passed = scoped_results.filter(mark__gte=PASS_MARK).count()
    return {
        "course_code": course.code,
        "course_name": course.name,
        "average_mark": _safe_round(scoped_results.aggregate(value=Avg("mark"))["value"]),
        "pass_rate": _safe_round((passed / total_results * 100) if total_results else None),
        "students": scoped_results.values("registration__student_id").distinct().count(),
    }


def _build_at_risk_context(filters: dict) -> dict:
    """Return top at-risk students in scope with risk scores and bands.
    Mirrors get_at_risk_students() from the standalone prototype.
    Only called when the message is about at-risk / watchlist students.
    """
    from collections import defaultdict as _dd

    candidate_regs = list(
        _base_registrations(filters)
        .filter(Q(carrying__gt=0) | ~Q(decision="") & Q(decision__isnull=False))
        .select_related("student", "programme")
        .prefetch_related("course_results")
    )

    # Keep only the latest registration per student
    latest_map: dict = {}
    for reg in candidate_regs:
        sid = reg.student_id
        if sid not in latest_map or (reg.period.external_id, reg.id) > (
            latest_map[sid].period.external_id, latest_map[sid].id
        ):
            latest_map[sid] = reg

    rows = []
    for reg in latest_map.values():
        marks = [float(r.mark) for r in reg.course_results.all() if r.mark is not None]
        avg = round(sum(marks) / len(marks), 1) if marks else None
        failed = sum(1 for m in marks if m < PASS_MARK)
        carrying = int(reg.carrying or 0)
        decision = str(reg.decision or "").strip().lower()
        risk = _risk_score_for_chat(avg, failed, carrying, decision)
        if risk["band"] == "low":
            continue
        rows.append({
            "registration_number": reg.student.registration_number,
            "name": reg.student.full_name,
            "programme": reg.programme.name if reg.programme else "Unknown",
            "band": risk["band"],
            "score": risk["score"],
            "drivers": ", ".join(risk.get("driver_labels", [])) or "none",
            "decision": str(reg.decision or "").title(),
            "average_mark": avg,
        })

    rows.sort(key=lambda x: -x["score"])
    band_counts: dict = _dd(int)
    for r in rows:
        band_counts[r["band"]] += 1

    return {
        "total_at_risk": len(rows),
        "band_counts": dict(band_counts),
        "top_students": rows[:MAX_AT_RISK_ROWS],
    }


def _build_course_difficulty_context(results) -> dict | None:
    """Return hardest and easiest courses ranked by average mark.
    Mirrors get_hardest_courses() from the standalone prototype.
    Only called when the message mentions course difficulty.
    """
    course_rows = list(
        results.values("course__code", "course__name")
        .annotate(
            avg_mark=Avg("mark"),
            student_count=Count("registration__student_id", distinct=True),
        )
        .filter(student_count__gte=5)
        .order_by("avg_mark")[: MAX_COURSE_ROWS * 2]
    )
    if not course_rows:
        return None

    sorted_rows = sorted(course_rows, key=lambda x: float(x["avg_mark"] or 0))
    hardest = [
        {
            "code": r["course__code"],
            "name": r["course__name"],
            "avg_mark": _safe_round(r["avg_mark"]),
            "classification": _classify_mark(_safe_round(r["avg_mark"])),
        }
        for r in sorted_rows[:MAX_COURSE_ROWS]
    ]
    easiest = [
        {
            "code": r["course__code"],
            "name": r["course__name"],
            "avg_mark": _safe_round(r["avg_mark"]),
            "classification": _classify_mark(_safe_round(r["avg_mark"])),
        }
        for r in reversed(sorted_rows[-MAX_COURSE_ROWS:])
    ]
    return {"hardest": hardest, "easiest": easiest}


def _build_year_distribution_context(filters: dict) -> dict:
    """Return student counts and gender breakdown by academic year.
    Mirrors year_gender from the standalone prototype's _compute_demographic_data().
    """
    from collections import defaultdict as _dd

    year_rows = list(
        _apply_scope_filters(Registration.objects.all(), filters)
        .exclude(period__academic_year="")
        .exclude(period__academic_year__isnull=True)
        .values("period__academic_year", "student__gender")
        .annotate(count=Count("student_id", distinct=True))
        .order_by("period__academic_year")
    )

    year_map: dict = _dd(lambda: {"male": 0, "female": 0, "unspecified": 0, "total": 0})
    for row in year_rows:
        yr = str(row["period__academic_year"])
        g = str(row["student__gender"] or "").strip().lower()
        if g.startswith("m"):
            year_map[yr]["male"] += row["count"]
        elif g.startswith("f"):
            year_map[yr]["female"] += row["count"]
        else:
            year_map[yr]["unspecified"] += row["count"]
        year_map[yr]["total"] += row["count"]

    return {
        "by_year": [
            {"year": yr, **counts}
            for yr, counts in sorted(year_map.items())
        ]
    }


_PERIOD_MONTH_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{4}\b",
    re.IGNORECASE,
)
_SEMESTER_RE = re.compile(r"\b(semester|sem)\s*[12]\b", re.IGNORECASE)


def _build_period_performance_context(message: str, filters: dict) -> dict | None:
    """Return per-period performance metrics matching a named period in the message.
    Mirrors _get_period_performance() from the standalone prototype.
    Returns None when no period name is detected in the message.
    """
    month_match = _PERIOD_MONTH_RE.search(message)
    if not month_match:
        return None

    # Use the matched month+year as a substring filter against period names
    period_token = month_match.group(0).strip()

    # Find matching AcademicPeriod objects
    matching_periods = list(
        AcademicPeriod.objects.filter(name__icontains=period_token)
    )
    if not matching_periods:
        return None
    period_name = matching_periods[0].name  # use canonical name

    scoped_regs = _apply_scope_filters(
        Registration.objects.filter(period__in=matching_periods)
        .select_related("student", "programme__department__faculty"),
        filters,
    )
    scoped_results = (
        CourseResult.objects
        .filter(registration__in=scoped_regs)
        .exclude(mark__isnull=True)
    )

    total_marks = scoped_results.count()
    if not total_marks:
        return None

    marks_list = list(scoped_results.values_list("mark", flat=True))
    avg_mark = _safe_round(sum(marks_list) / len(marks_list))
    pass_count = sum(1 for m in marks_list if m >= PASS_MARK)
    pass_rate = _safe_round(pass_count / total_marks * 100)
    fail_rate = _safe_round((total_marks - pass_count) / total_marks * 100)
    total_students = scoped_regs.values("student_id").distinct().count()

    # Decision breakdown
    from collections import Counter as _Counter
    dec_counter = _Counter(
        str(r.decision or "").strip().title()
        for r in scoped_regs.iterator()
        if r.decision
    )
    at_risk_total = sum(
        v for k, v in dec_counter.items()
        if k.lower() in HIGH_RISK_DECISIONS
    )
    proceeding_total = sum(
        v for k, v in dec_counter.items()
        if "proceed" in k.lower()
    )

    # Per-programme breakdown
    prog_rows = list(
        scoped_results
        .values("registration__programme__code", "registration__programme__name")
        .annotate(
            avg_mark=Avg("mark"),
            total=Count("id"),
            passed=Count("id", filter=Q(mark__gte=PASS_MARK)),
        )
        .order_by("-total")[:10]
    )
    by_programme = {
        row["registration__programme__code"]: {
            "name": row["registration__programme__name"],
            "avg_mark": _safe_round(row["avg_mark"]),
            "pass_rate": _safe_round(row["passed"] / row["total"] * 100) if row["total"] else None,
            "count": row["total"],
        }
        for row in prog_rows
    }

    return {
        "period": period_name,
        "total_students": total_students,
        "total_marks": total_marks,
        "avg_mark": avg_mark,
        "pass_rate": pass_rate,
        "fail_rate": fail_rate,
        "decisions": dict(dec_counter.most_common(8)),
        "at_risk_total": at_risk_total,
        "proceeding_total": proceeding_total,
        "by_programme": by_programme,
    }


_TOP_STUDENT_KWS = (
    "top student", "best student", "top perform", "best perform",
    "highest mark", "highest average", "highest scoring",
    "number one student", "top scorer", "best scorer",
    "who is the top", "who is the best", "who has the highest",
    "which student has", "leading student",
)
_TOP_STUDENT_SIGNAL_KWS = ("top", "best", "highest", "perform", "leading", "number one")
# Matches "top students", "top 5 students", "best 3 students", "highest 10 students"
_TOP_STUDENT_N_RE = re.compile(r"\b(top|best|highest)\s+\d*\s*students?\b", re.IGNORECASE)
# Captures the count in "top 5 students" → group(2) = "5"
_TOP_N_COUNT_RE = re.compile(r"\b(top|best|highest)\s+(\d+)\s*students?\b", re.IGNORECASE)


def _is_top_student_query(msg_lower: str) -> bool:
    """Return True when the message is asking for the best/top-performing student(s)."""
    if any(kw in msg_lower for kw in _TOP_STUDENT_KWS):
        return True
    if _TOP_STUDENT_N_RE.search(msg_lower):
        return True
    return ("who" in msg_lower or "which student" in msg_lower) and any(
        kw in msg_lower for kw in _TOP_STUDENT_SIGNAL_KWS
    )


def _build_top_student_context(filters: dict, message: str, programme_code: str = "") -> dict:
    """Return the top-N students by average mark within the current scope.

    Extracts an optional year-level filter (e.g. "year 2") and an optional
    count (e.g. "top 5") from the message and layers them on top of the
    existing topbar scope filters.  programme_code narrows the query to a
    specific programme (e.g. "ACCT") when supplied by a tool call.
    """
    msg_lower = message.lower()

    # How many students to return — default 5, capped at 20
    count_match = _TOP_N_COUNT_RE.search(message)
    top_n = min(max(int(count_match.group(2)), 1), 20) if count_match else 5

    year_filter = None
    for yr in (5, 4, 3, 2, 1):
        if f"year {yr}" in msg_lower:
            year_filter = yr
            break

    active_filters = {**filters}
    if year_filter and not active_filters.get("year"):
        active_filters["year"] = str(year_filter)

    registrations = _base_registrations(active_filters)
    if programme_code:
        registrations = registrations.filter(programme__code__iexact=programme_code)
    results = CourseResult.objects.filter(registration__in=registrations).exclude(mark__isnull=True)

    top_rows = list(
        results
        .values(
            "registration__student__registration_number",
            "registration__student__first_names",
            "registration__student__surname",
            "registration__programme__name",
            "registration__programme__code",
            "registration__student__gender",
        )
        .annotate(
            avg_mark=Avg("mark"),
            total_results=Count("id"),
        )
        .filter(total_results__gte=2)
        .order_by("-avg_mark")[:top_n]
    )

    students = []
    for row in top_rows:
        avg = _safe_round(row["avg_mark"])
        name = (
            f"{row['registration__student__first_names'] or ''} "
            f"{row['registration__student__surname'] or ''}"
        ).strip()
        students.append({
            "regnum": row["registration__student__registration_number"],
            "name": name or "Unknown",
            "programme": row["registration__programme__name"] or "Unknown",
            "code": row["registration__programme__code"] or "?",
            "gender": (row["registration__student__gender"] or "Unspecified").title(),
            "avg_mark": avg,
            "total_results": row["total_results"],
            "classification": _classify_mark(avg),
        })

    return {
        "students": students,
        "requested_count": top_n,
        "year_filter": year_filter,
        "scope_label": _build_scope_label(active_filters),
    }


def _build_lightweight_scope_summary(filters: dict) -> dict:
    """Three-query scope overview used by the tool-calling system prompt.

    Deliberately avoids the expensive parts of _summarize_scope (watchlist,
    faculty breakdown, programme breakdown) since the AI fetches those on
    demand via the registered tools.
    """
    registrations = _base_registrations(filters)
    results = CourseResult.objects.filter(registration__in=registrations).exclude(mark__isnull=True)
    total_students = registrations.values("student_id").distinct().count()
    total_results = results.count()
    avg_mark = results.aggregate(value=Avg("mark"))["value"]
    return {
        "filters": filters,
        "total_students": total_students,
        "total_results": total_results,
        "average_mark": _safe_round(avg_mark),
    }


def _execute_tool(name: str, args: dict, filters: dict) -> str:
    """Execute a registered tool call by name and return a JSON-encoded result.

    Each branch maps to an existing context builder so we reuse all existing
    DB query logic — tools are routing, not new queries.
    """
    try:
        if name == "search_top_students":
            count = min(max(int(args.get("count", 5)), 1), 20)
            year = args.get("year_level")
            prog_code = str(args.get("programme_code", "")).strip()
            faculty_name = args.get("faculty", "")
            eff = {**filters}
            if year:
                eff["year"] = str(year)
            if faculty_name:
                eff["faculty"] = faculty_name
            fake_msg = f"top {count} students" + (f" year {year}" if year else "")
            return json.dumps(
                _build_top_student_context(eff, fake_msg, programme_code=prog_code),
                default=str,
            )

        if name == "get_student_profile":
            regnum = str(args.get("registration_number", "")).strip()
            data = _build_student_context(regnum)
            return json.dumps(data or {"error": f"No student found for {regnum!r}"}, default=str)

        if name == "search_at_risk_students":
            data = _build_at_risk_context(filters) or {}
            band = str(args.get("risk_band", "")).lower()
            if band and data.get("top_students"):
                data = {
                    **data,
                    "top_students": [s for s in data["top_students"] if s.get("band", "").lower() == band],
                }
            return json.dumps(data, default=str)

        if name == "get_programme_statistics":
            codes = args.get("programme_codes") or []
            matched = (
                _match_entities(" ".join(codes), Programme, "name", "code")
                if codes
                else list(Programme.objects.filter(
                    registrations__in=_base_registrations(filters)
                ).distinct()[:MAX_PROGRAMME_ROWS])
            )
            return json.dumps(_build_programme_context(matched, filters), default=str)

        if name == "get_faculty_statistics":
            fname = args.get("faculty_name", "")
            matched = (
                _match_entities(fname, Faculty, "name")
                if fname
                else list(Faculty.objects.filter(
                    departments__programmes__registrations__in=_base_registrations(filters)
                ).distinct()[:MAX_FACULTY_ROWS])
            )
            return json.dumps(_build_faculty_context(matched, filters), default=str)

        if name == "get_demographic_breakdown":
            year = args.get("year_level")
            eff = {**filters}
            if year:
                eff["year"] = str(year)
            return json.dumps(_build_year_distribution_context(eff) or {}, default=str)

        if name == "get_course_difficulty_ranking":
            regs = _base_registrations(filters)
            results = CourseResult.objects.filter(registration__in=regs).exclude(mark__isnull=True)
            return json.dumps(_build_course_difficulty_context(results) or {}, default=str)

        if name == "get_period_performance":
            period_name = str(args.get("period_name", ""))
            return json.dumps(_build_period_performance_context(period_name, filters) or {}, default=str)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Tool execution error [%s]: %s", name, exc)
        return json.dumps({"error": str(exc)})

    return json.dumps({"error": f"Unknown tool: {name}"})


def _build_tool_system_text(scope: dict) -> str:
    """Lean system prompt for the tool-calling path.

    Unlike the rule-based system text, we do NOT pre-load the full context
    JSON — the AI calls tools to fetch exactly the data it needs.  This
    prevents the AI from being anchored to a pre-computed 'baseline answer'
    that may not match what the user actually asked.
    """
    scope_label = _build_scope_label(scope.get("filters", {}))
    return (
        "You are UniStudio Bot — a friendly, knowledgeable academic analytics assistant for the "
        "UniStudio registrar platform at Manicaland State University of Applied Sciences (MSUAS), Zimbabwe.\n\n"
        "PERSONALITY:\n"
        "- Speak in first person ('I can see...', 'Looking at the data...', 'I'd recommend...').\n"
        "- Be warm and conversational, not robotic. Write like a helpful colleague.\n"
        "- After the core answer, offer one relevant follow-up question.\n"
        "- CRITICAL: When the user says 'yes', 'sure', 'show me more', or any short affirmative — "
        "call the appropriate tool to fetch the data you previously offered. "
        "Do NOT summarise scope statistics instead.\n"
        "- Use short paragraphs. Never write a long run-on sentence.\n\n"
        "TOOL USAGE RULES:\n"
        "1. ALWAYS call a tool to fetch data — never invent or estimate numbers.\n"
        "2. COMPOUND QUERIES — when the user's question requires multiple pieces of data, "
        "call ALL needed tools before synthesising. Examples:\n"
        "   - 'top student in year 2 from the best programme' → call get_programme_statistics "
        "(find the top programme), THEN call search_top_students with that programme_code and year_level=2.\n"
        "   - 'compare ACCT and INSY pass rates then show top student' → call get_programme_statistics "
        "for both codes, THEN call search_top_students with the winner's code.\n"
        "   You may issue multiple tool calls in a single response — do so whenever you need more than "
        "one dataset to fully answer the question. Do NOT synthesise until you have all the data.\n"
        "3. For follow-up messages ('yes', 'which ones', 'tell me more'), "
        "look at the last assistant turn in the conversation history to determine "
        "which tool to call (e.g. call get_student_profile if you offered a profile).\n"
        "4. If data is unavailable after calling the appropriate tool, "
        "redirect to pr@msuas.ac.zw or +263 2063456.\n"
        "5. Stay within MSUAS academics, student performance, services, and admissions.\n\n"
        f"University facts: {json.dumps(UNIVERSITY_FACTS, ensure_ascii=True)}\n"
        f"Admissions: {ADMISSIONS_SUMMARY}\n"
        f"Completion rules: {COMPLETION_RULES_SUMMARY}\n"
        f"Risk bands: {RISK_BANDS_SUMMARY}\n"
        f"Current scope: {scope_label} — "
        f"{scope.get('total_students', '?')} students, "
        f"{scope.get('total_results', '?')} marks recorded, "
        f"avg mark {scope.get('average_mark', 'N/A')}.\n"
    )


def _build_scope_context(message: str, filters: dict):
    registrations = _base_registrations(filters)
    results = CourseResult.objects.filter(registration__in=registrations).exclude(mark__isnull=True)
    scope_summary = _summarize_scope(filters, registrations, results)

    student_targets = [_build_student_context(rn) for rn in _find_student_targets(message)]
    student_targets = [row for row in student_targets if row]
    programme_targets = _build_programme_context(
        _match_entities(message, Programme, "name", "code"),
        filters,
    )
    faculty_targets = _build_faculty_context(
        _match_entities(message, Faculty, "name"),
        filters,
    )
    course_target = _build_course_context(message, filters)

    # Conditional contexts — only run expensive queries when the message warrants it
    msg_lower = message.lower()
    at_risk_context = (
        _build_at_risk_context(filters)
        if any(kw in msg_lower for kw in ("at risk", "at-risk", "risk", "watchlist", "failing", "struggling"))
        else None
    )
    course_difficulty = (
        _build_course_difficulty_context(results)
        if any(kw in msg_lower for kw in ("hardest", "easiest", "difficult", "tough", "lowest mark", "highest mark", "course rank"))
        else None
    )
    period_performance = (
        _build_period_performance_context(message, filters)
        if _PERIOD_MONTH_RE.search(message)
        else None
    )
    _wants_distribution = (
        any(kw in msg_lower for kw in ("year", "year 1", "year 2", "year 3", "year 4", "distribution", "demographic", "gender"))
        and not _is_top_student_query(msg_lower)
    )
    year_distribution = _build_year_distribution_context(filters) if _wants_distribution else None

    top_student_context = (
        _build_top_student_context(filters, message)
        if _is_top_student_query(msg_lower)
        else None
    )

    return {
        "scope_summary": scope_summary,
        "student_targets": student_targets,
        "programme_targets": programme_targets,
        "faculty_targets": faculty_targets,
        "course_target": course_target,
        "at_risk_context": at_risk_context,
        "course_difficulty": course_difficulty,
        "period_performance": period_performance,
        "year_distribution": year_distribution,
        "top_student_context": top_student_context,
    }


def _build_history_block(history: list[dict] | None) -> str:
    lines = []
    for row in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = str(row.get("role", "")).strip().lower()
        content = _truncate(row.get("content", ""), 280)
        if role not in {"user", "assistant"} or not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n".join(lines) if lines else "No prior conversation."


def _extract_regnum_from_history(history: list[dict] | None) -> str | None:
    """Return the most recently mentioned registration number from the last assistant turn.

    When the user gives a short follow-up like "yes" after the bot offered
    "Would you like a detailed profile for LARONAH (M213TX)?", this lets us
    re-fetch that student's context so the AI has the actual data to respond with.
    """
    if not history:
        return None
    for turn in reversed(history):
        if turn.get("role") == "assistant":
            match = REGNUM_PATTERN.search(turn.get("content", ""))
            if match:
                return match.group(0)
    return None


def _is_contextual_reply(message: str, history: list[dict] | None) -> bool:
    """Return True when the message is a short follow-up to an existing conversation.

    Used to skip the greeting / out-of-scope short-circuits so replies like
    'yes', 'sure', 'go ahead', or 'which ones?' are handled by the AI with
    full conversation history rather than being mis-classified as greetings.
    """
    if not history:
        return False
    if not any(h.get("role") == "assistant" for h in history):
        return False
    cleaned = message.strip().lower()
    # Very short messages are nearly always contextual when a conversation exists
    if len(cleaned) <= 20:
        return True
    # Slightly longer messages — check for follow-up tokens
    words = set(re.split(r"\W+", cleaned))
    return bool(words & _FOLLOWUP_TOKENS) and len(cleaned) <= 120


def _build_google_contents(history: list[dict] | None, user_turn: str) -> list[dict]:
    """Build a multi-turn contents array for the Google Gemini API.

    Sends the last N history turns as alternating user/model entries so the
    model has genuine conversation context — not just embedded text.
    """
    contents = []
    for h in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = str(h.get("role", "")).lower()
        text = _truncate(h.get("content", ""), 400)
        if not text:
            continue
        api_role = "model" if role == "assistant" else "user"
        contents.append({"role": api_role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": user_turn}]})
    return contents


def _build_openai_messages(
    system_text: str, history: list[dict] | None, user_turn: str,
) -> list[dict]:
    """Build a multi-turn messages list for the OpenAI Chat Completions API."""
    messages: list[dict] = [{"role": "system", "content": system_text}]
    for h in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = str(h.get("role", "")).lower()
        text = _truncate(h.get("content", ""), 400)
        if role not in {"user", "assistant"} or not text:
            continue
        messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": user_turn})
    return messages


def _build_scope_label(filters: dict) -> str:
    parts = []
    if filters.get("year"):
        parts.append(f"Year {filters['year']}")
    if filters.get("period"):
        parts.append(f"Period {filters['period']}")
    if filters.get("faculty"):
        parts.append(f"Faculty {filters['faculty']}")
    return ", ".join(parts) if parts else "All visible records"


# ---------------------------------------------------------------------------
# Reply handlers — each returns str if it fires, None to fall through
# Signature: (message_lower, scope, scope_label, context) -> str | None
# ---------------------------------------------------------------------------

_COMPARE_KEYWORDS = (
    "compare", "comparison", "versus", " vs ", "rank",
    "strongest", "best performing", "top programme",
)


def _reply_safety_gate(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if any(re.search(pattern, message_lower) for pattern in SENSITIVE_PATTERNS):
        return (
            "I cannot help with secrets, credentials, or security bypass requests. "
            "I can help with student performance, programme analytics, admissions guidance, and platform data."
        )
    return None


def _reply_greeting(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _greeting_kws = (
        "hello", "hi", "hey", "good morning", "good afternoon",
        "good evening", "thanks", "thank you", "greetings",
    )
    if any(re.search(rf"\b{re.escape(kw)}\b", message_lower) for kw in _greeting_kws):
        return GREETING_REPLY
    return None


def _reply_out_of_scope(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _oos_kws = (
        "weather", "recipe", "cook", "cooking", "sport", "football", "cricket",
        "rugby", "movie", "film", "music", "song", "joke", "politics",
        "stock", "crypto", "bitcoin",
    )
    if any(re.search(rf"\b{re.escape(kw)}\b", message_lower) for kw in _oos_kws):
        return OUT_OF_SCOPE_REPLY
    return None


def _reply_student_lookup(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if not context["student_targets"]:
        return None
    student = context["student_targets"][0]
    recent_courses = ", ".join(
        f"{row['course_code']} {row['mark']}"
        for row in student["recent_courses"][:4]
        if row["course_code"]
    ) or "No recent course marks recorded."
    risk = student.get("risk", {})
    risk_drivers = ", ".join(risk.get("driver_labels", [])) or "none identified"
    completion_summary = ", ".join(
        (
            f"{row['period']}: {row['completion']}%"
            if row["completion"] > 0
            else f"{row['period']}: 0% ({row.get('zero_reason') or 'unknown reason'})"
        )
        for row in student.get("period_completions", [])
        if row.get("period")
    ) or "No completion data."
    avg_disp = student["average_mark"] if student["average_mark"] is not None else "N/A"
    return (
        f"{student['registration_number']} — {student['name']} ({student['gender']}). "
        f"Programme: {student['programme']} ({student['faculty']}). "
        f"Latest period: {student['latest_period']}. "
        f"Decision: {student['latest_decision'] or 'Not recorded'}, carrying: {student['carrying']}. "
        f"Average mark: {avg_disp} — {student['classification']}. "
        f"Risk: {risk.get('band', 'unknown').title()} (score {risk.get('score', 0)}) — {risk_drivers}. "
        f"Graduation rate: {student.get('graduation_rate', 'N/A')}%. "
        f"Completion by period: {completion_summary} "
        f"Recent courses: {recent_courses}."
    )


def _reply_at_risk(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    arc = context.get("at_risk_context")
    if not arc:
        return None
    bands = arc["band_counts"]
    band_str = ", ".join(f"{k.title()}: {v}" for k, v in bands.items()) or "none identified"
    top = arc["top_students"]
    total = arc["total_at_risk"]
    if total == 0:
        return (
            f"Good news — looking at {scope_label}, I'm not seeing any students above the low-risk threshold right now. "
            f"The watchlist still shows {scope['watchlist_count']} students flagged for multi-fail or carrying, "
            f"so it's worth keeping an eye on those. Would you like me to pull up the full watchlist breakdown?"
        )
    student_lines = "\n".join(
        f"  • {s['registration_number']} — {s['name']} ({s['programme']}, {s['band'].title()} risk, score {s['score']})"
        for s in top[:5]
    )
    return (
        f"Here's what I'm seeing for {scope_label} — and it's worth paying attention to.\n\n"
        f"There are {total} students at moderate risk or above. "
        f"Risk band breakdown: {band_str}.\n\n"
        f"Top students by risk score:\n{student_lines}\n\n"
        f"Would you like me to look deeper into any of these students, or break the risk down by programme or faculty?"
    )


def _reply_comparison(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if len(context["programme_targets"]) < 2:
        return None
    programmes = context["programme_targets"]
    ranked = sorted(programmes, key=lambda p: float(p["pass_rate"] or 0), reverse=True)
    best = ranked[0]
    worst = ranked[-1]
    lines = "\n".join(
        f"  {i+1}. {p['name']} — pass rate {_format_pct(p['pass_rate'])}, "
        f"avg mark {p['average_mark'] if p['average_mark'] is not None else 'N/A'}, "
        f"{p['students']} students"
        for i, p in enumerate(ranked)
    )
    gap = (
        round(float(best["pass_rate"] or 0) - float(worst["pass_rate"] or 0), 1)
        if best["pass_rate"] is not None and worst["pass_rate"] is not None else None
    )
    gap_note = (
        f" There's a {gap}% pass rate gap between the top and bottom programme — worth investigating."
        if gap else ""
    )
    return (
        f"Here's how those programmes compare within {scope_label}, ranked by pass rate:\n\n"
        f"{lines}\n\n"
        f"{best['name']} comes out on top.{gap_note}\n\n"
        f"Would you like me to look at the at-risk students or decision breakdown for any of these?"
    )


def _reply_comparison_top_scope(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    """Fallback comparison when no specific programmes were named."""
    is_compare = any(kw in message_lower for kw in _COMPARE_KEYWORDS)
    if not is_compare or context["programme_targets"]:
        return None
    top = scope.get("top_programmes", [])
    if not top:
        return None
    ranked = sorted(top, key=lambda p: float(p["pass_rate"] or 0), reverse=True)
    best = ranked[0]
    lines = "\n".join(
        f"  {i+1}. {p['name']} ({p.get('code', '?')}) — pass rate {_format_pct(p['pass_rate'])}, "
        f"avg {p['average_mark'] if p['average_mark'] is not None else 'N/A'}, "
        f"{p['students']} students"
        for i, p in enumerate(ranked)
    )
    return (
        f"Here are the top programmes in {scope_label}, ranked by pass rate:\n\n"
        f"{lines}\n\n"
        f"{best['name']} is leading the pack right now. "
        f"To compare specific programmes side by side, just name them — e.g. 'Compare ACCT vs BMAN vs INSY'."
    )


def _reply_course_difficulty(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    cd = context.get("course_difficulty")
    if not cd:
        return None
    hardest_lines = ", ".join(
        f"{c['code']} ({c['avg_mark']})" for c in cd["hardest"][:5]
    ) or "N/A"
    easiest_lines = ", ".join(
        f"{c['code']} ({c['avg_mark']})" for c in cd["easiest"][:5]
    ) or "N/A"
    return (
        f"Within the current scope ({scope_label}): "
        f"Hardest courses by average mark — {hardest_lines}. "
        f"Easiest courses — {easiest_lines}."
    )


def _reply_completion_rules(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if "completion" in message_lower and any(
        kw in message_lower for kw in ("rule", "explain", "mean", "how", "calculate")
    ):
        return COMPLETION_RULES_SUMMARY
    return None


def _reply_graduation_rules(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if "graduation" in message_lower and any(
        kw in message_lower for kw in ("rule", "explain", "mean", "how", "calculate", "stage")
    ):
        return GRADUATION_RULES_SUMMARY
    return None


def _reply_admissions(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _admission_kws = ("apply", "admission", "entry requirement", "enrol", "enroll", "requirement")
    if any(kw in message_lower for kw in _admission_kws):
        return ADMISSIONS_SUMMARY
    return None


def _reply_student_services(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _services_kws = (
        "service", "accommodation", "health", "sport", "disability",
        "short course", "new programme", "2026",
    )
    if any(kw in message_lower for kw in _services_kws):
        return STUDENT_SERVICES_SUMMARY
    return None


def _reply_contact(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _contact_kws = (
        "phone", "email", "contact", "where is", "location", "portal",
        "library", "direction", "timetable", "founded", "history", "verification",
    )
    if not any(kw in message_lower for kw in _contact_kws):
        return None
    return (
        f"{UNIVERSITY_FACTS['name']} — founded {UNIVERSITY_FACTS['founded']}. "
        f"Location: {UNIVERSITY_FACTS['location']}. "
        f"Directions: {UNIVERSITY_FACTS['directions']} "
        f"Contact: {UNIVERSITY_FACTS['phone']} | {UNIVERSITY_FACTS['email']}. "
        f"Website: {UNIVERSITY_FACTS['website']}. "
        f"Portals: student {UNIVERSITY_FACTS['student_portal']}, "
        f"timetable {UNIVERSITY_FACTS['teaching_timetable']}, "
        f"library {UNIVERSITY_FACTS['library']}, "
        f"certificate verification {UNIVERSITY_FACTS['certificate_verification']}."
    )


def _reply_single_programme(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if not context["programme_targets"]:
        return None
    programme = context["programme_targets"][0]
    return (
        f"Within the current scope ({scope_label}), {programme['name']} ({programme['faculty']}) has "
        f"{programme['students']} students across {programme['registrations']} registrations. "
        f"Average mark: {programme['average_mark'] if programme['average_mark'] is not None else 'N/A'}, "
        f"pass rate: {_format_pct(programme['pass_rate'])}."
    )


def _reply_faculty(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if not context["faculty_targets"]:
        return None
    faculty = context["faculty_targets"][0]
    return (
        f"Within the current scope ({scope_label}), {faculty['faculty']} has "
        f"{faculty['students']} students across {faculty['registrations']} registrations. "
        f"Average mark: {faculty['average_mark'] if faculty['average_mark'] is not None else 'N/A'}, "
        f"pass rate: {_format_pct(faculty['pass_rate'])}."
    )


def _reply_single_course(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    course = context.get("course_target")
    if not course:
        return None
    return (
        f"For {course['course_code']} — {course['course_name']} in scope ({scope_label}): "
        f"average mark {course['average_mark'] if course['average_mark'] is not None else 'N/A'}, "
        f"pass rate {_format_pct(course['pass_rate'])} across {course['students']} students."
    )


def _reply_risk_summary(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _risk_kws = ("risk", "at-risk", "watchlist", "failing", "struggling")
    if not any(kw in message_lower for kw in _risk_kws):
        return None
    gender_str = ", ".join(
        f"{g}: {d['count']} ({d['pct']}%)" for g, d in scope.get("gender_breakdown", {}).items()
    )
    return (
        f"In the current scope ({scope_label}), {scope['watchlist_count']} students are on the watchlist "
        f"({scope['multi_fail_count']} with 2+ failures, {scope['carrying_count']} carrying, "
        f"{scope['adverse_decision_count']} with adverse decisions) "
        f"out of {scope['total_students']} total."
        + (f" Gender breakdown: {gender_str}." if gender_str else "")
    )


def _reply_decisions(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _decision_kws = ("decision", "proceed", "retake", "repeat", "deferred", "discontinue")
    if not any(kw in message_lower for kw in _decision_kws):
        return None
    decision_lines = ", ".join(
        f"{row['decision']} ({row['count']})" for row in scope["top_decisions"]
    ) or "No decision data."
    proceeding_pct = scope.get("proceeding_pct")
    at_risk_pct = scope.get("at_risk_pct")
    return (
        f"Decision breakdown in scope ({scope_label}): {decision_lines}. "
        f"Proceeding: {scope.get('proceeding_count', 0)} students"
        + (f" ({proceeding_pct}%)" if proceeding_pct is not None else "")
        + f". Adverse decisions: {scope['adverse_decision_count']}"
        + (f" ({at_risk_pct}% of students)" if at_risk_pct is not None else "")
        + "."
    )


def _reply_top_student(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    tsc = context.get("top_student_context")
    if not tsc:
        return None

    students = tsc["students"]
    yr_info = f" in Year {tsc['year_filter']}" if tsc["year_filter"] else ""
    effective_label = tsc["scope_label"]

    if not students:
        return (
            f"I couldn't find any student performance data{yr_info} in the current scope "
            f"({effective_label}). This may mean no marks have been recorded yet."
        )

    top = students[0]
    count_label = tsc.get("requested_count", len(students))
    lines = "\n".join(
        f"  {i + 1}. {s['name']} ({s['regnum']}) — {s['programme']} ({s['code']}) | "
        f"avg {s['avg_mark']} | {s['classification']}"
        for i, s in enumerate(students)
    )
    first_name = top["name"].split()[0] if top["name"] != "Unknown" else "this student"
    return (
        f"Top {count_label} performing students{yr_info} in scope ({effective_label}):\n\n"
        f"  1st: {top['name']} ({top['regnum']}) — {top['programme']} ({top['code']})\n"
        f"  Average mark: {top['avg_mark']} ({top['classification']})\n\n"
        f"Full ranking:\n{lines}\n\n"
        f"Source: live DB query — avg mark across all recorded course results, min 2 results. "
        f"Would you like a detailed profile for {first_name}?"
    )


def _reply_demographics(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    _demo_kws = ("gender", "male", "female", "demographic", "year", "distribution")
    if not any(kw in message_lower for kw in _demo_kws):
        return None
    if _is_top_student_query(message_lower):
        return None

    # Year distribution — answer first if the question is about academic years
    if any(kw in message_lower for kw in ("year 1", "year 2", "year 3", "year 4", "year distribution", "by year")):
        yd = context.get("year_distribution")
        if yd and yd.get("by_year"):
            lines = []
            for row in yd["by_year"]:
                g = row
                lines.append(
                    f"  {row['year']}: {row['total']} students "
                    f"(Male {g['male']}, Female {g['female']}"
                    + (f", Unspecified {g['unspecified']}" if g["unspecified"] else "")
                    + ")"
                )
            return (
                f"Student distribution by academic year in scope ({scope_label}):\n"
                + "\n".join(lines)
            )

    # Per-faculty breakdown when a faculty was matched
    faculty_ctx = context.get("faculty_targets") or []
    if faculty_ctx:
        lines = []
        for fac in faculty_ctx:
            fac_gender = fac.get("gender_breakdown", {})
            if fac_gender:
                g_str = ", ".join(
                    f"{g}: {d['count']} ({d['pct']}%)" for g, d in fac_gender.items()
                )
                lines.append(f"{fac['faculty']}: {fac['students']} students — {g_str}.")
        if lines:
            return "Gender breakdown by faculty:\n" + "\n".join(lines)

    # Per-programme breakdown when a programme was matched
    programme_ctx = context.get("programme_targets") or []
    if programme_ctx:
        lines = []
        for prog in programme_ctx:
            prog_gender = prog.get("gender_breakdown", {})
            if prog_gender:
                g_str = ", ".join(
                    f"{g}: {d['count']} ({d['pct']}%)" for g, d in prog_gender.items()
                )
                lines.append(
                    f"{prog['name']} ({prog['code']}): {prog['students']} students — {g_str}."
                )
        if lines:
            return "Gender breakdown by programme:\n" + "\n".join(lines)

    # Scope-level gender totals + year distribution if available
    gender_str = ", ".join(
        f"{g}: {d['count']} ({d['pct']}%)" for g, d in scope.get("gender_breakdown", {}).items()
    )
    total = scope["total_students"]
    reply = (
        f"Gender breakdown in scope ({scope_label}) across {total} students: "
        f"{gender_str if gender_str else 'No gender data available'}."
    )
    yd = context.get("year_distribution")
    if yd and yd.get("by_year"):
        year_lines = ", ".join(
            f"{row['year']}: {row['total']}" for row in yd["by_year"]
        )
        reply += f" By academic year: {year_lines}."
    return reply


def _reply_period_performance(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str | None:
    if not (_PERIOD_MONTH_RE.search(message_lower) or _SEMESTER_RE.search(message_lower)):
        return None
    period_ctx = context.get("period_performance")
    if period_ctx:
        prog_lines = "; ".join(
            f"{code}: avg {d['avg_mark']}, pass {_format_pct(d['pass_rate'])}"
            for code, d in list(period_ctx["by_programme"].items())[:6]
        ) or "No programme breakdown available."
        dec_lines = ", ".join(
            f"{k} ({v})" for k, v in list(period_ctx["decisions"].items())[:6]
        ) or "None."
        return (
            f"Period '{period_ctx['period']}': "
            f"{period_ctx['total_students']} students, {period_ctx['total_marks']} marks recorded. "
            f"Average mark: {period_ctx['avg_mark'] if period_ctx['avg_mark'] is not None else 'N/A'}, "
            f"pass rate: {_format_pct(period_ctx['pass_rate'])}, "
            f"fail rate: {_format_pct(period_ctx['fail_rate'])}. "
            f"Proceeding: {period_ctx.get('proceeding_total', 0)}, "
            f"at-risk: {period_ctx.get('at_risk_total', 0)}. "
            f"Decisions: {dec_lines} "
            f"Programme breakdown: {prog_lines}."
        )
    period_names = ", ".join(scope.get("available_periods", [])) or "not available in current scope"
    return (
        f"Period performance within scope ({scope_label}): "
        f"overall average mark {scope['average_mark'] if scope['average_mark'] is not None else 'N/A'}, "
        f"pass rate {_format_pct(scope['pass_rate'])} across {scope['total_students']} students. "
        f"To narrow to a specific period use the Period filter in the top bar. "
        f"Available periods in this scope: {period_names}."
    )


def _reply_default(
    message_lower: str, scope: dict, scope_label: str, context: dict,
) -> str:
    top_programme = scope["top_programmes"][0]["name"] if scope["top_programmes"] else "no dominant programme"
    top_faculty = scope["top_faculties"][0]["faculty"] if scope["top_faculties"] else "no dominant faculty"
    gender_str = ", ".join(
        f"{g}: {d['count']} ({d['pct']}%)" for g, d in scope.get("gender_breakdown", {}).items()
    )
    median_disp = scope.get("median_mark")
    avg_disp = scope["average_mark"] if scope["average_mark"] is not None else "N/A"
    return (
        f"Here's a snapshot of what I'm seeing for {scope_label}:\n\n"
        f"We have {scope['total_students']} students across {scope['total_registrations']} registrations, "
        f"with {scope['total_results']} recorded marks. "
        f"The average mark is {avg_disp}"
        + (f" (median {median_disp})" if median_disp is not None else "")
        + f", and the overall pass rate sits at {_format_pct(scope['pass_rate'])}.\n\n"
        f"On the risk side, {scope['watchlist_count']} students are flagged — "
        f"{scope['multi_fail_count']} with multiple fails, {scope['carrying_count']} carrying, "
        f"and {scope['adverse_decision_count']} with adverse decisions.\n\n"
        + (f"Gender breakdown: {gender_str}.\n\n" if gender_str else "")
        + f"The busiest faculty is {top_faculty}, and the largest programme is {top_programme}.\n\n"
        f"Is there anything specific you'd like me to dig into — a particular programme, faculty, or student?"
    )


# Ordered list of handlers — first non-None result wins.
_REPLY_HANDLERS = (
    _reply_safety_gate,
    _reply_greeting,
    _reply_out_of_scope,
    _reply_student_lookup,
    _reply_at_risk,
    _reply_comparison,
    _reply_comparison_top_scope,
    _reply_course_difficulty,
    _reply_completion_rules,
    _reply_graduation_rules,
    _reply_admissions,
    _reply_student_services,
    _reply_contact,
    _reply_single_programme,
    _reply_faculty,
    _reply_single_course,
    _reply_risk_summary,
    _reply_decisions,
    _reply_top_student,
    _reply_demographics,
    _reply_period_performance,
)


def _build_rule_based_reply(message: str, context: dict) -> str:
    """Dispatch to the first matching reply handler, falling back to the default scope summary."""
    message_lower = str(message or "").lower()
    scope = context["scope_summary"]
    scope_label = _build_scope_label(scope["filters"])
    args = (message_lower, scope, scope_label, context)
    for handler in _REPLY_HANDLERS:
        result = handler(*args)
        if result is not None:
            return result
    return _reply_default(*args)


def _build_programme_table(context: dict) -> str:
    """Build a compact programme reference table for the AI system prompt.
    Mirrors the prog_lines block in the prototype's build_system_prompt().
    """
    rows = context.get("scope_summary", {}).get("top_programmes", [])
    if not rows:
        return "No programme data in current scope."
    lines = []
    for p in rows:
        pass_r = _format_pct(p.get("pass_rate"))
        avg = p.get("average_mark", "N/A")
        carrying = p.get("carrying_count", 0)
        fail_r = _format_pct(p.get("fail_rate"))
        lines.append(
            f"  {p.get('code', '?')}: {p.get('name', '?')} | "
            f"pass {pass_r} | fail {fail_r} | avg {avg} | "
            f"students {p.get('students', 0)} | carrying {carrying}"
        )
    return "\n".join(lines)


def _build_system_text(context: dict, fallback_reply: str) -> str:
    """Return the system-level prompt: instructions + all data context + baseline.

    History is intentionally excluded — it is sent as genuine conversation turns
    via _build_google_contents / _build_openai_messages so the model maintains a
    real thread rather than reading a flat transcript.
    """
    programme_table = _build_programme_table(context)
    return (
        "You are UniStudio Bot — a friendly, knowledgeable academic analytics assistant for the "
        "UniStudio registrar platform at Manicaland State University of Applied Sciences (MSUAS), Zimbabwe.\n\n"
        "PERSONALITY:\n"
        "- Speak in first person ('I can see...', 'Looking at the data...', 'I'd recommend...').\n"
        "- Be warm and conversational, not robotic. Write like a helpful colleague.\n"
        "- Acknowledge the question naturally before diving into data.\n"
        "- After the core answer, offer one relevant follow-up question.\n"
        "- CRITICAL: You are in a multi-turn conversation. If the user says 'yes', 'sure', 'go ahead', "
        "'which ones', or any short affirmative/follow-up, you MUST deliver on the follow-up you offered "
        "in your previous reply — do NOT start a new topic or re-introduce yourself.\n"
        "- When data shows something concerning, acknowledge the human impact briefly.\n"
        "- Use short paragraphs. Never write a long run-on sentence.\n\n"
        "ACCURACY RULES:\n"
        "1. Use only the supplied facts and scope context. Never invent numbers.\n"
        "2. If data is unavailable, redirect to pr@msuas.ac.zw or +263 2063456.\n"
        "3. Show step-by-step working for any calculation.\n"
        "4. When comparing programmes or faculties, always rank them.\n"
        "5. Stay within MSUAS academics, student performance, services, and admissions.\n\n"
        f"University facts: {json.dumps(UNIVERSITY_FACTS, ensure_ascii=True)}\n"
        f"Admissions: {ADMISSIONS_SUMMARY}\n"
        f"Student services: {STUDENT_SERVICES_SUMMARY}\n"
        f"Completion rules: {COMPLETION_RULES_SUMMARY}\n"
        f"Graduation rules: {GRADUATION_RULES_SUMMARY}\n"
        f"Risk bands: {RISK_BANDS_SUMMARY}\n"
        f"Programme reference table:\n{programme_table}\n"
        f"Current scoped data: {json.dumps(context, ensure_ascii=True, default=str)}\n"
        f"Baseline answer (factual foundation — rewrite conversationally): {fallback_reply}\n"
    )


def _build_user_turn(message: str) -> str:
    return f"User question: {message}"


def _openai_tool_call_round(
    system_text: str,
    history: list[dict] | None,
    user_turn: str,
    filters: dict,
    emit,
) -> str | None:
    """Multi-round OpenAI tool-calling exchange.

    Loops until the model returns finish_reason='stop' (or max 4 rounds).
    Each round: model either calls tools (we execute them and continue) or
    produces a final text reply (we return it).
    """
    _HEADERS = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"}
    messages = _build_openai_messages(system_text, history, user_turn)

    for round_num in range(4):
        payload = {
            "model": settings.CHATBOT_OPENAI_MODEL,
            "max_tokens": 800,
            "messages": messages,
            "tools": CHATBOT_TOOLS,
            "tool_choice": "auto",
        }
        req = urllib.request.Request(
            OPENAI_CHAT_COMPLETIONS_URL,
            data=json.dumps(payload).encode(),
            headers=_HEADERS,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=settings.CHATBOT_TIMEOUT_SECONDS) as r:
                raw = json.loads(r.read().decode())
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI tool-call round %d failed: %s", round_num + 1, exc)
            return None

        choice = raw.get("choices", [{}])[0]
        assistant_msg = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")
        tool_calls = assistant_msg.get("tool_calls") or []

        if finish_reason != "tool_calls" or not tool_calls:
            # Model is done — return whatever text it produced
            return (assistant_msg.get("content") or "").strip() or None

        # Execute each tool call and append results before the next round
        emit("Fetching data from database…")
        messages.append(assistant_msg)
        for tc in tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            result = _execute_tool(fn.get("name", ""), args, filters)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    logger.warning("OpenAI tool-call exceeded max rounds without a final reply")
    return None


def _google_tool_call_round(
    system_text: str,
    history: list[dict] | None,
    user_turn: str,
    filters: dict,
    emit,
) -> str | None:
    """Two-pass Google Gemini function-calling exchange.

    Pass 1 — send message + function declarations; model returns functionCall parts.
    Pass 2 — send functionResponse parts; model synthesises the final reply.
    Returns the final text or None on any failure.
    """
    def _upcase(schema: dict) -> dict:
        out = {}
        for k, v in schema.items():
            if k == "type" and isinstance(v, str):
                out[k] = v.upper()
            elif k == "properties" and isinstance(v, dict):
                out[k] = {pk: _upcase(pv) for pk, pv in v.items()}
            elif k == "items" and isinstance(v, dict):
                out[k] = _upcase(v)
            else:
                out[k] = v
        return out

    google_tools = [{"functionDeclarations": [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "parameters": _upcase(t["function"]["parameters"]),
        }
        for t in CHATBOT_TOOLS
    ]}]

    url = GOOGLE_GENERATE_CONTENT_URL_TEMPLATE.format(model=settings.CHATBOT_GOOGLE_MODEL)
    headers = {"Content-Type": "application/json", "x-goog-api-key": settings.GOOGLE_API_KEY}
    contents = _build_google_contents(history, user_turn)

    payload1 = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "tools": google_tools,
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 800},
    }
    req1 = urllib.request.Request(url, data=json.dumps(payload1).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req1, timeout=settings.CHATBOT_TIMEOUT_SECONDS) as r:
            raw1 = json.loads(r.read().decode())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google tool-call pass 1 failed: %s", exc)
        return None

    parts = raw1.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    fn_calls = [p["functionCall"] for p in parts if "functionCall" in p]

    if not fn_calls:
        return _extract_google_response_text(raw1).strip() or None

    emit("Fetching data from database…")
    contents.append({"role": "model", "parts": parts})
    for fc in fn_calls:
        result_str = _execute_tool(fc.get("name", ""), fc.get("args", {}), filters)
        contents.append({
            "role": "user",
            "parts": [{"functionResponse": {"name": fc["name"], "response": json.loads(result_str)}}],
        })

    payload2 = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 800},
    }
    req2 = urllib.request.Request(url, data=json.dumps(payload2).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req2, timeout=settings.CHATBOT_TIMEOUT_SECONDS) as r:
            raw2 = json.loads(r.read().decode())
        return _extract_google_response_text(raw2).strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google tool-call pass 2 failed: %s", exc)
        return None


def _request_openai_chatbot_response(
    system_text: str,
    history: list[dict] | None,
    user_turn: str,
) -> str:
    """Call OpenAI Chat Completions with a proper multi-turn message array."""
    payload = {
        "model": settings.CHATBOT_OPENAI_MODEL,
        "max_tokens": 600,
        "messages": _build_openai_messages(system_text, history, user_turn),
    }
    request = urllib.request.Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.CHATBOT_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def _request_google_chatbot_response(
    system_text: str,
    history: list[dict] | None,
    user_turn: str,
) -> str:
    """Call Google Gemini with a proper multi-turn contents array."""
    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": _build_google_contents(history, user_turn),
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 600,
        },
    }
    request = urllib.request.Request(
        GOOGLE_GENERATE_CONTENT_URL_TEMPLATE.format(model=settings.CHATBOT_GOOGLE_MODEL),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GOOGLE_API_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.CHATBOT_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def _detect_intent(message: str, status: dict) -> dict:
    """Classify message intent via a fast, low-token AI call.

    Uses Google Gemini (preferred) or OpenAI Chat Completions with a 5-second
    timeout and a maximum of 80 output tokens — cheap and sub-second in practice.
    Falls back to ``{"intent": "general_info", "entities": {}}`` on any error so
    the main reply pipeline always proceeds.
    """
    _FALLBACK: dict = {"intent": "general_info", "entities": {}}
    payload_text = f"Message: {message[:400]}"

    try:
        if status.get("google_ready"):
            payload = {
                "systemInstruction": {"parts": [{"text": INTENT_PROMPT}]},
                "contents": [{"parts": [{"text": payload_text}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 80},
            }
            req = urllib.request.Request(
                GOOGLE_GENERATE_CONTENT_URL_TEMPLATE.format(model=settings.CHATBOT_GOOGLE_MODEL),
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": settings.GOOGLE_API_KEY,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            text = _extract_google_response_text(raw).strip()
            result = json.loads(text)
            if "intent" in result:
                return result

        elif status.get("openai_ready"):
            payload = {
                "model": "gpt-4o-mini",
                "temperature": 0,
                "max_tokens": 80,
                "messages": [
                    {"role": "system", "content": INTENT_PROMPT},
                    {"role": "user", "content": payload_text},
                ],
            }
            req = urllib.request.Request(
                OPENAI_CHAT_COMPLETIONS_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            text = raw["choices"][0]["message"]["content"].strip()
            result = json.loads(text)
            if "intent" in result:
                return result

    except Exception as exc:  # noqa: BLE001
        logger.debug("Intent detection failed (non-fatal): %s", exc)

    return _FALLBACK


def get_chatbot_reply(
    message: str,
    filters: dict | None = None,
    history: list[dict] | None = None,
    status_callback=None,
    session_id: str | None = None,
) -> dict:
    """Return a chatbot reply dict.

    Args:
        message: Raw user message text.
        filters: Topbar scope filters (year/period/faculty).
        history: Prior conversation turns for the AI context window.
        status_callback: Optional callable(step: str) invoked at each processing
            stage so callers can stream progress to the user.
        session_id: Django session key used to persist per-session context.
    """

    def _emit(step: str) -> None:
        if callable(status_callback):
            try:
                status_callback(step)
            except Exception:  # noqa: BLE001
                pass

    cleaned_message = _truncate(message)
    if not cleaned_message:
        raise ValueError("A message is required.")

    filters = _normalize_filters(filters)
    status = get_chatbot_provider_status()

    diagnostics = {
        "provider": status["provider"],
        "ai_available": status["ai_available"],
        "returned_source": "rules",
        "fallback_reason": "",
        "intent": None,
    }

    # Detect contextual follow-ups BEFORE intent classification.
    is_contextual = _is_contextual_reply(cleaned_message, history)

    # --- Intent detection (Layer 2) ----------------------------------------
    intent = "general_info"
    intent_entities: dict = {}
    if status["enabled"] and status["ai_available"]:
        _emit("Analysing your question\u2026")
        intent_result = _detect_intent(cleaned_message, status)
        intent = intent_result.get("intent", "general_info")
        intent_entities = intent_result.get("entities", {})
        diagnostics["intent"] = intent

        if not is_contextual:
            if intent == "greeting":
                return {
                    "reply": GREETING_REPLY,
                    "source": "rules",
                    "source_label": PROVIDER_LABELS["rules"],
                    "diagnostics": diagnostics,
                }
            if intent == "out_of_scope":
                return {
                    "reply": OUT_OF_SCOPE_REPLY,
                    "source": "rules",
                    "source_label": PROVIDER_LABELS["rules"],
                    "diagnostics": diagnostics,
                }

    # --- Tool-calling path (primary when AI is available) -------------------
    # The AI selects which DB function(s) to call, executes them, then
    # synthesises the answer -- no keyword dispatch, no pre-loaded context blob.
    if status["enabled"] and status["ai_available"]:
        _emit("Querying the database\u2026")
        scope = _build_lightweight_scope_summary(filters)
        system_text = _build_tool_system_text(scope)
        user_turn = _build_user_turn(cleaned_message)
        _emit("Preparing your answer\u2026")
        response_text = None
        try:
            if status["openai_ready"]:
                _emit("Connecting to OpenAI\u2026")
                response_text = _openai_tool_call_round(
                    system_text, history, user_turn, filters, _emit
                )
                if response_text:
                    diagnostics["returned_source"] = "openai"
            elif status["google_ready"]:
                _emit("Connecting to Google Gemini\u2026")
                response_text = _google_tool_call_round(
                    system_text, history, user_turn, filters, _emit
                )
                if response_text:
                    diagnostics["returned_source"] = "google"
            else:
                diagnostics["fallback_reason"] = "no_ai_provider_configured"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            logger.warning("Tool-calling round failed: %s", error)
            diagnostics["fallback_reason"] = "tool_calling_failed"

        if response_text:
            _store_session_ctx(session_id, {
                "last_reply": response_text,
                "filters": filters,
                "intent": intent,
            })
            source = diagnostics["returned_source"]
            return {
                "reply": response_text,
                "source": source,
                "source_label": PROVIDER_LABELS.get(source, source),
                "diagnostics": diagnostics,
            }

        if not diagnostics["fallback_reason"]:
            diagnostics["fallback_reason"] = "tool_calling_empty_response"

    # --- Rule-based path (chatbot disabled OR tool-calling failed) ----------
    _emit("Querying the database\u2026")
    context = _build_scope_context(cleaned_message, filters)
    context["_intent"] = intent
    context["_intent_entities"] = intent_entities

    if intent == "at_risk" and not context.get("at_risk_context"):
        _emit("Analysing at-risk students\u2026")
        context["at_risk_context"] = _build_at_risk_context(filters)
    elif context.get("at_risk_context"):
        _emit("Analysing at-risk students\u2026")

    if intent == "demographic" and not context.get("faculty_targets") and intent_entities.get("faculty"):
        matched = _match_entities(intent_entities["faculty"], Faculty, "name")
        if matched:
            context["faculty_targets"] = _build_faculty_context(matched, filters)

    if intent == "data_query" and not context.get("course_difficulty"):
        msg_lower_check = cleaned_message.lower()
        if any(kw in msg_lower_check for kw in ("hard", "easy", "difficult", "tough")):
            _emit("Checking course difficulty\u2026")
            context["course_difficulty"] = _build_course_difficulty_context(
                CourseResult.objects.filter(
                    registration__in=_base_registrations(filters)
                ).exclude(mark__isnull=True)
            )
    elif context.get("course_difficulty"):
        _emit("Checking course difficulty\u2026")

    if intent == "data_query" and not context.get("top_student_context"):
        if _is_top_student_query(cleaned_message.lower()):
            _emit("Finding top performers\u2026")
            context["top_student_context"] = _build_top_student_context(filters, cleaned_message)
    elif context.get("top_student_context"):
        _emit("Finding top performers\u2026")

    if context.get("student_targets"):
        _emit("Looking up student records\u2026")

    if context.get("programme_targets"):
        _emit("Looking up programme data\u2026")

    _emit("Preparing your answer\u2026")

    if is_contextual:
        _prev_regnum = _extract_regnum_from_history(history)
        if _prev_regnum and not context.get("student_targets"):
            _emit("Looking up student records\u2026")
            _recovered = _build_student_context(_prev_regnum)
            if _recovered:
                context["student_targets"] = [_recovered]
        fallback_reply = (
            "This is a follow-up to the previous answer. "
            "Do NOT re-summarise overall scope data. "
            "Use the conversation history to determine exactly what the user is affirming or "
            "asking about, then respond directly and specifically to that request."
        )
    else:
        fallback_reply = _build_rule_based_reply(cleaned_message, context)

    if not status["enabled"]:
        diagnostics["fallback_reason"] = "chatbot_disabled"
        return {
            "reply": fallback_reply,
            "source": "rules",
            "source_label": PROVIDER_LABELS["rules"],
            "diagnostics": diagnostics,
        }

    system_text = _build_system_text(context, fallback_reply)
    user_turn   = _build_user_turn(cleaned_message)

    try:
        if status["google_ready"]:
            _emit("Connecting to Google Gemini\u2026")
            raw_response = _request_google_chatbot_response(system_text, history, user_turn)
            response_text = _extract_google_response_text(json.loads(raw_response))
            if response_text:
                diagnostics["returned_source"] = "google"
                return {
                    "reply": response_text,
                    "source": "google",
                    "source_label": PROVIDER_LABELS["google"],
                    "diagnostics": diagnostics,
                }
            diagnostics["fallback_reason"] = "empty_google_response"
        elif status["openai_ready"]:
            _emit("Connecting to OpenAI\u2026")
            raw_response = _request_openai_chatbot_response(system_text, history, user_turn)
            response_text = _extract_response_text(json.loads(raw_response))
            if response_text:
                diagnostics["returned_source"] = "openai"
                return {
                    "reply": response_text,
                    "source": "openai",
                    "source_label": PROVIDER_LABELS["openai"],
                    "diagnostics": diagnostics,
                }
            diagnostics["fallback_reason"] = "empty_openai_response"
        else:
            diagnostics["fallback_reason"] = "no_ai_provider_configured"
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.warning("Chatbot provider request failed: %s", error)
        diagnostics["fallback_reason"] = "provider_request_failed"

    return {
        "reply": fallback_reply,
        "source": "rules",
        "source_label": PROVIDER_LABELS["rules"],
        "diagnostics": diagnostics,
    }

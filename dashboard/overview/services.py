"""Service-layer logic for the story-first landing dashboard."""

import math
from collections import Counter, defaultdict
from urllib.parse import urlencode

from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.urls import reverse

from ..risk.services import build_student_risk_profiles_from_registrations
from ..views import (
    RETENTION_EXIT_DECISIONS,
    format_academic_level_label,
    get_filtered_registrations,
    normalize_decision_label,
    normalize_gender_key,
)
from .constants import OVERVIEW_SUMMARY_CARD_SPECS, PROGRESS_STATUS_CONFIG, RISK_BAND_CONFIG

OVERVIEW_CACHE_TTL_SECONDS = 30
DEFAULT_DRILLDOWN_PAGE_SIZE = 100
MAX_DRILLDOWN_PAGE_SIZE = 100


def _is_first_semester_value(value):
    """Return whether a raw semester value should count as first semester."""

    semester_text = str(value or "").strip().lower()
    if not semester_text:
        return False

    return (
        semester_text == "1"
        or semester_text.startswith("1")
        or semester_text.startswith("first")
        or "semester 1" in semester_text
        or "first year" in semester_text
    )


def _calculate_first_year_retention(registrations):
    """Calculate First Year Retention rate based on student progression across semesters."""

    registrations = list(registrations)
    if not registrations:
        return "No data available"

    filtered_student_ids = set()
    filtered_period_ids_by_student = defaultdict(set)

    for registration in registrations:
        filtered_student_ids.add(registration.student_id)
        if registration.period_id:
            filtered_period_ids_by_student[registration.student_id].add(registration.period_id)

    from dashboard.models import Registration

    registration_history = (
        Registration.objects.filter(student_id__in=filtered_student_ids)
        .order_by("student_id", "created_at", "id")
        .values("student_id", "period_id")
    )
    first_period_by_student = {}
    registration_counts = Counter()

    for history_row in registration_history:
        student_id = history_row["student_id"]
        registration_counts[student_id] += 1
        first_period_by_student.setdefault(student_id, history_row["period_id"])

    first_year_student_ids = [
        student_id
        for student_id in filtered_student_ids
        if first_period_by_student.get(student_id) in filtered_period_ids_by_student[student_id]
    ]

    if not first_year_student_ids:
        return "No data available"

    progressed_students = sum(
        1
        for student_id in first_year_student_ids
        if registration_counts.get(student_id, 0) > 1
    )
    retention_rate = _pct(progressed_students, len(first_year_student_ids))
    return f"{retention_rate}%"


def _extract_academic_year(period):
    """Extract academic year from period name."""
    if not period or not period.name:
        return None
    
    period_name = str(period.name).lower()
    
    # For period names like "September 2023 - December 2023"
    # Extract the first year as the academic year
    import re
    
    # Look for year patterns in the period name
    year_matches = re.findall(r'\b(20[0-9]{2})\b', period_name)
    if year_matches:
        # Use the first year found as the academic year
        year = int(year_matches[0])
        
        # Map calendar years to academic years based on your data (years 1-5)
        # Updated mapping based on your 2020 = Academic Year 1
        if year == 2020:
            return 1  # 2020 is academic year 1
        elif year == 2021:
            return 2  # 2021 is academic year 2
        elif year == 2022:
            return 3  # 2022 is academic year 3
        elif year == 2023:
            return 4  # 2023 is academic year 4
        elif year == 2024:
            return 5  # 2024 is academic year 5
        elif year == 2025:
            return 6  # 2025 is academic year 6
        else:
            # For other years, calculate relative to 2020
            return year - 2019
    
    return None


def _extract_semester(period):
    """Extract semester from period name."""
    if not period or not period.name:
        return None
    
    period_name = str(period.name).lower()
    
    # Handle both CSV format (AUGUST 2025 - DECEMBER 2025) and filter format (August-December)
    
    # August-December patterns (Semester 2 - second half of academic year)
    if ('august' in period_name and 'december' in period_name) or \
       ('september' in period_name and 'december' in period_name):
        return 2  # August-December or September-December is Semester 2
    
    # March-July patterns (Semester 1 - first half of academic year)
    elif ('march' in period_name and 'july' in period_name) or \
         ('may' in period_name and 'july' in period_name):
        return 1  # March-July or May-July is Semester 1
    
    # May-August patterns (Semester 1)
    elif 'may' in period_name and 'august' in period_name:
        return 1  # May-August is Semester 1
    
    # October-March patterns (Semester 2)
    elif 'october' in period_name and 'march' in period_name:
        return 2  # October-March is Semester 2
    
    # January-April patterns (could be Semester 1)
    elif 'january' in period_name and 'april' in period_name:
        return 1  # January-April could be Semester 1
    
    # Fallback to original logic for other patterns
    import re
    semester_match = re.search(r'(?:semester|sem)\s*([0-9]+)', period_name)
    if semester_match:
        return int(semester_match.group(1))
    
    if 'first' in period_name or '1st' in period_name:
        return 1
    elif 'second' in period_name or '2nd' in period_name:
        return 2
    elif 'third' in period_name or '3rd' in period_name:
        return 3
    
    return None


def _calculate_students_satisfaction(marked_results):
    """Calculate Students Satisfaction based on performance metrics."""

    if not marked_results["marked_count"]:
        return "0%"

    total_results = marked_results["marked_count"]
    high_performers = marked_results["high_performer_count"]
    average_mark = marked_results["average_mark"] or 0

    performance_score = _pct(high_performers, total_results)
    average_score = min(100, round((average_mark / 100) * 100))

    satisfaction_score = round((performance_score * 0.7) + (average_score * 0.3))
    return f"{satisfaction_score}%"


def _pct(count, total):
    """Return a rounded percentage while safely handling empty totals."""

    return round((count / total) * 100) if total else 0


def _format_count(value):
    """Format integers with grouping for short note copy."""

    return f"{int(value or 0):,}"


def _format_mark_display(value):
    """Return a compact display string for optional mark values."""

    if value is None:
        return "--"
    return str(round(value))


def _build_student_detail_url(request, detail_slug):
    """Build a student-detail link that keeps the current filter scope."""

    base_url = reverse("dashboard:student-detail", args=[detail_slug])
    filter_pairs = []
    for key in ("year", "period", "faculty"):
        for value in request.GET.getlist(key):
            cleaned_value = str(value or "").strip()
            if cleaned_value:
                filter_pairs.append((key, cleaned_value))

    if not filter_pairs:
        return base_url

    return f"{base_url}?{urlencode(filter_pairs, doseq=True)}"


def _build_outcome_student_profiles(registrations, request=None):
    """Build one student-level outcome record per visible student for chart drill-downs."""

    profiles = []
    student_outcomes = set()

    for registration in registrations:
        student_id = registration.student_id
        if student_id in student_outcomes:
            continue

        student_outcomes.add(student_id)
        marked_results_count = getattr(registration, "marked_results", None)
        awaiting_results_count = getattr(registration, "awaiting_results", None)
        average_mark = getattr(registration, "average_mark", None)

        if marked_results_count is None or awaiting_results_count is None:
            student_results = list(registration.course_results.all())
            if not student_results:
                continue

            marked_results = [result for result in student_results if result.mark is not None]
            awaiting_results = [result for result in student_results if result.mark is None]
            marked_results_count = len(marked_results)
            awaiting_results_count = len(awaiting_results)
            if marked_results_count:
                average_mark = sum(float(result.mark) for result in marked_results) / marked_results_count

        if marked_results_count == 0 and awaiting_results_count:
            status_key = "awaiting"
            status_label = "Awaiting Mark"
        elif marked_results_count and average_mark is not None:
            average_mark = float(average_mark)
            if average_mark >= 50:
                status_key = "passed"
                status_label = "Passed"
            else:
                status_key = "failed"
                status_label = "Failed"
        else:
            continue

        detail_slug = registration.student.registration_number.lower()
        profiles.append(
            {
                "student_id": student_id,
                "name": registration.student.full_name,
                "registration_number": registration.student.registration_number,
                "programme": registration.programme.name if registration.programme else "Unassigned",
                "average_mark": average_mark,
                "status_key": status_key,
                "status_label": status_label,
                "detail_url": _build_student_detail_url(request, detail_slug) if request else "",
            }
        )

    return profiles


def _build_result_summary(registrations):
    """Collapse prefetched course results into a reusable overview summary."""

    summary = {
        "total_count": 0,
        "marked_count": 0,
        "pass_count": 0,
        "fail_count": 0,
        "awaiting_count": 0,
        "high_performer_count": 0,
        "average_mark": 0,
    }
    total_mark_sum = 0
    outcome_profiles = _build_outcome_student_profiles(registrations)

    for profile in outcome_profiles:
        summary["total_count"] += 1

        if profile["status_key"] == "awaiting":
            summary["awaiting_count"] += 1
            continue

        if profile["average_mark"] is None:
            continue

        summary["marked_count"] += 1
        total_mark_sum += profile["average_mark"]

        if profile["status_key"] == "passed":
            summary["pass_count"] += 1
        elif profile["status_key"] == "failed":
            summary["fail_count"] += 1

        if profile["average_mark"] >= 60:
            summary["high_performer_count"] += 1

    if summary["marked_count"]:
        summary["average_mark"] = total_mark_sum / summary["marked_count"]

    return summary


def _get_registration_faculty_name(registration):
    """Return the faculty name associated with a registration."""

    department = registration.programme.department if registration.programme else None
    faculty = department.faculty if department else None
    return faculty.name if faculty else "Unassigned"


def build_overview_scope_pills(request):
    """Build compact scope pills describing the active landing-page filter context."""

    selected_faculty = request.GET.get("faculty", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_year = request.GET.get("year", "").strip()

    pills = [
        {
            "label": "Filtered overview" if any([selected_faculty, selected_period, selected_year]) else "Live overview",
            "variant": "live",
        }
    ]

    if selected_faculty:
        pills.append({"label": f"Faculty: {selected_faculty}", "variant": "scope"})
    if selected_period:
        pills.append({"label": f"Period: {selected_period}", "variant": "scope"})
    if selected_year:
        pills.append({"label": f"Year: {selected_year}", "variant": "scope"})

    if len(pills) == 1:
        pills.append({"label": "All faculties", "variant": "scope"})
        pills.append({"label": "All periods", "variant": "scope"})
        pills.append({"label": "All years", "variant": "scope"})

    return pills


def _build_summary_values(registrations, result_summary, risk_profiles):
    """Calculate the headline KPI values shown on the landing page."""

    total_registered = len(registrations)
    total_students = len({registration.student_id for registration in registrations})
    result_count = result_summary["marked_count"]
    pass_count = result_summary["pass_count"]
    average_mark = result_summary["average_mark"]
    proceed_count = sum(1 for registration in registrations if str(registration.decision or "").strip().lower().startswith("proceed"))
    on_time_count = sum(
        1
        for registration in registrations
        if str(registration.decision or "").strip().lower() == "proceed" and (registration.carrying == 0)
    )
    first_semester_count = sum(
        1 for registration in registrations if _is_first_semester_value(registration.period.semester if registration.period else "")
    )
    at_risk_count = sum(1 for row in risk_profiles if row["risk_level"] != "Low Risk")
    first_year_retention = _calculate_first_year_retention(registrations)
    students_satisfaction = _calculate_students_satisfaction(result_summary)

    completion_rate = (
        f"{round((proceed_count / total_registered) * 100)}%"
        if total_registered
        else "0%"
    )

    return {
        "enrolled": total_students,
        "registered": total_registered,
        "pass_rate": f"{round((pass_count / result_count) * 100)}%" if result_count else "0%",
        "completion_rate": completion_rate,
        "on_time_graduation": on_time_count,
        "first_year_retention": first_year_retention,
        "students_satisfaction": students_satisfaction,
        "average_mark": round(average_mark or 0),
        "first_semester": first_semester_count,
        "at_risk": at_risk_count,
    }


def _build_summary_cards(summary_values, faculty_load_rows, result_summary, risk_profiles):
    """Build the executive summary cards shown at the top of the landing page."""

    high_risk_count = sum(1 for row in risk_profiles if row["risk_level"] == "High Risk")
    medium_risk_count = sum(1 for row in risk_profiles if row["risk_level"] == "Medium Risk")
    result_count = result_summary["marked_count"]
    lead_faculty = faculty_load_rows[0] if faculty_load_rows else None

    notes = {
        "enrolled": (
            f"Unique students in current scope."
            if summary_values['enrolled']
            else "Student data will appear once registrations are available."
        ),
        "registered": (
            f"Total course registrations."
            if summary_values['registered']
            else "Registration data will appear once records are available."
        ),
        "pass_rate": (
            f"Of marked results, passed."
            if result_count
            else "Marked assessment results are not available yet."
        ),
        "completion_rate": (
            f"Completed their academic period."
            if summary_values['completion_rate']
            else "Completion data will be available once academic decisions are finalized."
        ),
        "on_time_graduation": (
            f"Progressing without delays."
            if summary_values['on_time_graduation']
            else "On-time graduation data will appear as students complete their programmes."
        ),
        "first_year_retention": (
            f"First-year student progression rate."
            if summary_values['first_year_retention'] != "0%"
            else "First-year retention data requires multiple semesters of student records."
        ),
        "students_satisfaction": (
            f"Based on academic performance."
            if summary_values['students_satisfaction'] != "0%"
            else "Student satisfaction requires sufficient assessment results for analysis."
        ),
        "at_risk": (
            f"{high_risk_count} high and {medium_risk_count} medium priority."
            if summary_values["at_risk"]
            else "No students are currently in medium or high-risk bands."
        ),
    }

    cards = []
    for spec in OVERVIEW_SUMMARY_CARD_SPECS:
        tone = spec["tone"]
        if spec["key"] == "pass_rate":
            pass_rate_value = int(str(summary_values["pass_rate"]).replace("%", "") or 0)
            if pass_rate_value < 60:
                tone = "danger"
            elif pass_rate_value >= 80:
                tone = "success"
        if spec["key"] == "at_risk" and not summary_values["at_risk"]:
            tone = "success"

        cards.append(
            {
                "key": spec["key"],
                "label": spec["label"],
                "tone": tone,
                "value": summary_values[spec["key"]],
                "note": notes.get(spec["key"], ""),
            }
        )
    return cards


def _build_outcome_rows(result_summary):
    """Aggregate visible assessment outcomes for the first landing-page chart."""

    # Use marked_count for denominator to match pass rate KPI calculation
    marked_results = result_summary["marked_count"]
    rows = [
        {
            "key": "passed",
            "label": "Passed",
            "count": result_summary["pass_count"],
            "percent": 0,
            "tone": "success",
        },
        {
            "key": "failed",
            "label": "Failed",
            "count": result_summary["fail_count"],
            "percent": 0,
            "tone": "danger",
        },
        {
            "key": "awaiting",
            "label": "Awaiting Mark",
            "count": result_summary["awaiting_count"],
            "percent": 0,
            "tone": "neutral",
        },
    ]

    # Calculate percentages based on marked results for consistency with KPI
    marked_rows = [row for row in rows if row["key"] in ["passed", "failed"]]
    for row in marked_rows:
        row["percent"] = _pct(row["count"], marked_results)
    
    # For awaiting marks, calculate percentage of total results
    awaiting_row = next((row for row in rows if row["key"] == "awaiting"), None)
    if awaiting_row and awaiting_row["count"] > 0:
        awaiting_row["percent"] = _pct(awaiting_row["count"], result_summary["total_count"])
    
    # Filter out rows with zero count
    filtered_rows = [row for row in rows if row["count"] > 0]
    return filtered_rows


def _build_risk_distribution_rows(risk_profiles):
    """Aggregate the visible student cohort into broad risk bands."""

    total_students = len(risk_profiles)
    rows = []

    for band in RISK_BAND_CONFIG:
        min_score = int(band["min_score"] or 0)
        max_score = band["max_score"]
        count = sum(
            1
            for row in risk_profiles
            if (int(row.get("risk_score", 0) or 0) >= min_score)
            and (max_score is None or int(row.get("risk_score", 0) or 0) <= int(max_score))
        )
        rows.append(
            {
                "key": band["key"],
                "label": band["label"],
                "count": count,
                "percent": _pct(count, total_students),
                "tone": band["tone"],
            }
        )

    return rows


def _build_faculty_load_rows(registrations):
    """Aggregate registration load by faculty for the landing-page capacity view."""

    faculty_counts = {}
    for registration in registrations:
        faculty_name = _get_registration_faculty_name(registration)
        faculty_counts[faculty_name] = faculty_counts.get(faculty_name, 0) + 1

    total_registrations = len(registrations)
    rows = [
        {
            "label": faculty_name,
            "registrations": count,
            "share_pct": _pct(count, total_registrations),
        }
        for faculty_name, count in sorted(faculty_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return rows[:6]


def _classify_progress_status(decision_label):
    """Map free-text registration decisions into stable landing-page buckets."""

    normalized = str(decision_label or "").strip().lower()
    if normalized == "proceed":
        return "proceed"
    if normalized in {"retake", "repeat", "supplementary", "supp"}:
        return "retake"
    if normalized in {"pending", "not recorded", "deferred"}:
        return "pending"
    if normalized in RETENTION_EXIT_DECISIONS:
        return "exit"
    return "other"


def _build_progress_rows(registrations):
    """Aggregate registration decisions into a clean progress-status chart."""

    status_counts = Counter()
    for registration in registrations:
        decision_label = normalize_decision_label(registration.decision)
        status_counts[_classify_progress_status(decision_label)] += 1

    total_registrations = len(registrations)
    rows = []
    for status in PROGRESS_STATUS_CONFIG:
        count = status_counts.get(status["key"], 0)
        if not count:
            continue

        rows.append(
            {
                "key": status["key"],
                "label": status["label"],
                "count": count,
                "share_pct": _pct(count, total_registrations),
                "tone": status["tone"],
            }
        )

    return rows


def _build_outcome_drilldown_payload(request, registrations, bucket_key, page, page_size):
    """Build the student table shown when a user drills into an outcome slice."""

    status_labels = {
        "passed": "Passed",
        "failed": "Failed",
        "awaiting": "Awaiting Mark",
    }
    if bucket_key not in status_labels:
        raise ValueError("Unsupported outcome drill-down bucket.")

    outcome_profiles = [
        profile for profile in _build_outcome_student_profiles(registrations, request)
        if profile["status_key"] == bucket_key
    ]

    if bucket_key == "passed":
        outcome_profiles.sort(key=lambda row: (-float(row["average_mark"] or 0), row["name"]))
    elif bucket_key == "failed":
        outcome_profiles.sort(key=lambda row: (float(row["average_mark"] or 0), row["name"]))
    else:
        outcome_profiles.sort(key=lambda row: (row["name"], row["registration_number"]))

    label = status_labels[bucket_key]
    payload = {
        "title": f"{label} Students",
        "subtitle": f"{_format_count(len(outcome_profiles))} students in the {label.lower()} outcome slice.",
        "columns": [
            {"key": "name", "label": "Student"},
            {"key": "registration_number", "label": "Student Number"},
            {"key": "programme", "label": "Programme"},
        ],
    }

    minimal_rows = [
        {
            "name": profile["name"],
            "registration_number": profile["registration_number"],
            "programme": profile["programme"],
            "detail_url": profile["detail_url"],
        }
        for profile in outcome_profiles
    ]
    return _build_paginated_payload(payload, minimal_rows, page, page_size)


def _build_risk_drilldown_payload(request, registrations, risk_profiles, bucket_key, page, page_size):
    """Build the student table shown when a user drills into a risk bar."""

    selected_band = next((band for band in RISK_BAND_CONFIG if band["key"] == bucket_key), None)
    if not selected_band:
        raise ValueError("Unsupported risk drill-down bucket.")

    min_score = int(selected_band["min_score"] or 0)
    max_score = selected_band["max_score"]
    minimal_rows = []

    for profile in risk_profiles:
        risk_score = int(profile.get("risk_score", 0) or 0)
        if risk_score < min_score:
            continue
        if max_score is not None and risk_score > int(max_score):
            continue

        minimal_rows.append(
            {
                "name": profile["name"],
                "registration_number": profile["registration_number"],
                "programme": profile["programme"],
                "detail_url": _build_student_detail_url(request, profile["detail_slug"]),
            }
        )

    payload = {
        "title": f"{selected_band['label']} Students",
        "subtitle": f"{_format_count(len(minimal_rows))} students in the {selected_band['label'].lower()} risk band.",
        "columns": [
            {"key": "name", "label": "Student"},
            {"key": "registration_number", "label": "Student Number"},
            {"key": "programme", "label": "Programme"},
        ],
    }

    return _build_paginated_payload(payload, minimal_rows, page, page_size)


def _parse_positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return parsed if parsed > 0 else default


def _build_paginated_payload(payload, rows, page, page_size):
    total_count = len(rows)
    page_size = max(1, min(page_size, MAX_DRILLDOWN_PAGE_SIZE))
    page_count = max(1, math.ceil(total_count / page_size)) if total_count else 1
    page = max(1, min(page, page_count))
    start = (page - 1) * page_size
    end = start + page_size

    payload.update(
        {
            "rows": rows[start:end],
            "page": page,
            "page_size": page_size,
            "page_count": page_count,
            "total_count": total_count,
        }
    )
    return payload


def _build_overview_drilldown_cache_key(request, chart_key, bucket_key, page, page_size):
    query_string = urlencode(
        sorted(
            (key, value)
            for key, values in request.GET.lists()
            if key not in ("page", "page_size")
            for value in values
        ),
        doseq=True,
    )
    return f"dashboard:overview:drilldown:{chart_key}:{bucket_key}:page={page}:size={page_size}:{query_string or 'all'}"


def _build_overview_drilldown_data(request, chart_key, bucket_key, page, page_size):
    """Return on-demand student rows for a landing-page chart drill-down."""

    registrations = get_filtered_registrations(request, include_course_results=True)

    if chart_key == "outcomes":
        return _build_outcome_drilldown_payload(request, registrations, bucket_key, page, page_size)

    if chart_key == "risk_distribution":
        risk_profiles = build_student_risk_profiles_from_registrations(registrations)
        return _build_risk_drilldown_payload(request, registrations, risk_profiles, bucket_key, page, page_size)

    raise ValueError("Unsupported overview drill-down chart.")


def build_overview_drilldown_data(request, chart_key, bucket_key):
    page = _parse_positive_int(request.GET.get("page"), 1)
    page_size = _parse_positive_int(request.GET.get("page_size"), DEFAULT_DRILLDOWN_PAGE_SIZE)
    cache_key = _build_overview_drilldown_cache_key(request, chart_key, bucket_key, page, page_size)

    return cache.get_or_set(
        cache_key,
        lambda: _build_overview_drilldown_data(request, chart_key, bucket_key, page, page_size),
        OVERVIEW_CACHE_TTL_SECONDS,
    )


def bust_overview_drilldown_caches():
    """Clear all overview drilldown caches. Call this when underlying student data changes."""

    cache.delete_many([
        key for key in (cache._cache.keys() if hasattr(cache, "_cache") else [])
        if isinstance(key, str) and key.startswith("dashboard:overview:drilldown:")
    ])


def bust_overview_drilldown_cache_for_request(request):
    """Clear drilldown caches for a specific filtered scope, chart, bucket, page, and size."""

    page = _parse_positive_int(request.GET.get("page"), 1)
    page_size = _parse_positive_int(request.GET.get("page_size"), DEFAULT_DRILLDOWN_PAGE_SIZE)

    for chart_key in ["outcomes", "risk_distribution"]:
        for bucket_key in ["passed", "failed", "awaiting", "critical", "high", "medium", "low"]:
            cache_key = _build_overview_drilldown_cache_key(request, chart_key, bucket_key, page, page_size)
            cache.delete(cache_key)


def _build_student_snapshot(registrations):
    """Collapse the filtered registrations into a unique student list."""

    students = {}
    for registration in registrations:
        students.setdefault(registration.student_id, registration.student)
    return list(students.values())


def _build_gender_rows(students):
    """Aggregate the visible cohort by normalized gender buckets."""

    gender_labels = {
        "male": "Male",
        "female": "Female",
        "unspecified": "Unspecified",
    }
    gender_counts = Counter(normalize_gender_key(student.gender) for student in students)
    total_students = len(students)

    rows = []
    for key in ("male", "female", "unspecified"):
        count = gender_counts.get(key, 0)
        if not count:
            continue
        rows.append(
            {
                "key": key,
                "label": gender_labels[key],
                "count": count,
                "share_pct": _pct(count, total_students),
            }
        )
    return rows


def _build_birth_location_rows(students):
    """Aggregate student birth locations for demographic jump-off context."""

    location_counts = Counter()
    for student in students:
        location = str(student.place_of_birth or "").strip()
        label = location.title() if location else "Unspecified"
        location_counts[label] += 1

    total_students = len(students)
    rows = [
        {
            "label": location,
            "count": count,
            "share_pct": _pct(count, total_students),
        }
        for location, count in sorted(location_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return rows


def _build_level_focus_snapshot(risk_profiles):
    """Return the academic-level concentration snapshot used on the action cards."""

    focus_rows = [row for row in risk_profiles if row["risk_level"] != "Low Risk"] or risk_profiles
    if not focus_rows:
        return None

    level_counts = Counter(row["academic_level"] for row in focus_rows)
    lead_label, lead_count = sorted(level_counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return {
        "label": lead_label,
        "count": lead_count,
        "share_pct": _pct(lead_count, len(focus_rows)),
        "mode": "watchlist" if any(row["risk_level"] != "Low Risk" for row in risk_profiles) else "cohort",
    }


def _pick_lead_location(location_rows):
    """Prefer a named location over an unspecified bucket for the action card copy."""

    if not location_rows:
        return None
    for row in location_rows:
        if row["label"] != "Unspecified":
            return row
    return location_rows[0]


def _pick_lead_gender(gender_rows):
    """Return the strongest named gender bucket for the action card copy."""

    if not gender_rows:
        return None
    for row in gender_rows:
        if row["key"] != "unspecified":
            return row
    return gender_rows[0]


def _build_action_cards(risk_profiles, faculty_load_rows, gender_rows, location_rows):
    """Build route cards that send users from the landing page into deeper workspaces."""

    at_risk_profiles = [row for row in risk_profiles if row["risk_level"] != "Low Risk"]
    high_risk_profiles = [row for row in risk_profiles if row["risk_level"] == "High Risk"]
    lead_faculty = faculty_load_rows[0] if faculty_load_rows else None
    lead_level = _build_level_focus_snapshot(risk_profiles)
    lead_location = _pick_lead_location(location_rows)
    lead_gender = _pick_lead_gender(gender_rows)

    return [
        {
            "kicker": "Risk",
            "title": "Review the active watchlist",
            "copy": (
                f"{_format_count(len(at_risk_profiles))} students currently need attention, including {_format_count(len(high_risk_profiles))} in the high-risk band."
                if at_risk_profiles
                else "No students are currently in the medium or high-risk bands, but the risk workspace remains the fastest way to review academic pressure."
            ),
            "action_label": "Open risk register",
            "action_url": reverse("dashboard:risk"),
            "tone": "danger" if at_risk_profiles else "success",
        },
        {
            "kicker": "Insights",
            "title": "Inspect the institutional pressure view",
            "copy": (
                f"{lead_faculty['label']} carries {lead_faculty['share_pct']}% of visible registrations, making it the clearest place to inspect system-wide pressure next."
                if lead_faculty
                else "Use insights to turn the landing-page signals into a deeper faculty-by-faculty operational read."
            ),
            "action_label": "Open insights",
            "action_url": reverse("dashboard:insights"),
            "tone": "primary",
        },
        {
            "kicker": "Academic Levels",
            "title": "Check where the academic journey bends",
            "copy": (
                f"{lead_level['label']} currently holds {lead_level['share_pct']}% of the visible {lead_level['mode']} load."
                if lead_level
                else "Open academic levels to compare cohort performance and pass-rate spread across the learning journey."
            ),
            "action_label": "Open academic levels",
            "action_url": reverse("dashboard:academic-level"),
            "tone": "warning",
        },
        {
            "kicker": "Demographics",
            "title": "Explore who makes up this cohort",
            "copy": (
                f"{lead_location['label']} is the largest visible birth-location group, while {lead_gender['label']} students represent {lead_gender['share_pct']}% of the cohort."
                if lead_location and lead_gender
                else "Open demographics to review cohort balance, location mix, and programme composition."
            ),
            "action_label": "Open demographics",
            "action_url": reverse("dashboard:demographic"),
            "tone": "info",
        },
    ]


def get_home_summary_values(request):
    """Return the headline metric values for the landing-page cards."""

    return get_cached_overview_dashboard_data(request)["summary_metrics"]


def build_overview_dashboard_data(request):
    """Assemble the real landing-page signals shown immediately after login."""

    registrations = list(get_filtered_registrations(request))
    result_summary = _build_result_summary(registrations)
    risk_profiles = build_student_risk_profiles_from_registrations(registrations)
    faculty_load_rows = _build_faculty_load_rows(registrations)
    students = _build_student_snapshot(registrations)
    gender_rows = _build_gender_rows(students)
    location_rows = _build_birth_location_rows(students)
    summary_values = _build_summary_values(registrations, result_summary, risk_profiles)

    return {
        "summary_metrics": summary_values,
        "summary_cards": _build_summary_cards(summary_values, faculty_load_rows, result_summary, risk_profiles),
        "scope_pills": build_overview_scope_pills(request),
        "outcome_rows": _build_outcome_rows(result_summary),
        "risk_distribution_rows": _build_risk_distribution_rows(risk_profiles),
        "faculty_load_rows": faculty_load_rows,
        "progress_rows": _build_progress_rows(registrations),
        "action_cards": _build_action_cards(risk_profiles, faculty_load_rows, gender_rows, location_rows),
    }


def _build_overview_cache_key(request):
    """Create a stable cache key for the current overview filter scope."""

    query_string = urlencode(sorted(request.GET.lists()), doseq=True)
    return f"dashboard:overview:{query_string or 'all'}"


def get_cached_overview_dashboard_data(request):
    """Return cached overview analytics for the current filter scope."""

    cache_key = _build_overview_cache_key(request)
    return cache.get_or_set(
        cache_key,
        lambda: build_overview_dashboard_data(request),
        OVERVIEW_CACHE_TTL_SECONDS,
    )

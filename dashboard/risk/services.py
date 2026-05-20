"""Service-layer logic for the risk dashboard feature."""

from urllib.parse import urlencode

from django.core.cache import cache
from django.db.models import Q

from ..views import format_academic_level_label, get_filtered_registrations, normalize_decision_label
from .constants import (
    HIGH_RISK_DECISIONS,
    RISK_BAND_DEFINITIONS,
    RISK_DRIVER_LABELS,
    RISK_DRIVER_PRIORITY,
    RISK_PRIORITY,
)

RISK_CACHE_TTL_SECONDS = 30
RISK_DRILLDOWN_COLUMNS = (
    {"key": "name", "label": "Student"},
    {"key": "programme", "label": "Programme"},
    {"key": "academic_level", "label": "Academic Level"},
    {"key": "average_mark", "label": "Average Mark"},
    {"key": "failed_courses", "label": "Failed Modules"},
    {"key": "total_modules", "label": "Total Modules"},
    {"key": "carrying", "label": "Carrying"},
    {"key": "decision", "label": "Decision"},
    {"key": "risk_level", "label": "Risk Status"},
)
RISK_DRILLDOWN_BAND_LABELS = {
    "low": "Low Risk (0-1)",
    "moderate": "Medium Risk (2-3)",
    "high": "High Risk (4-5)",
    "critical": "Critical (6+)",
}


def _safe_int(value, fallback=999):
    """Convert mixed academic year or semester values into sortable integers."""

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def _format_share_pct(count, total):
    """Return a rounded percentage for chart labels and narratives."""

    return round((count / total) * 100) if total else 0


def _match_band(score, band):
    """Check whether a numeric risk score belongs to a configured band."""

    min_score = int(band.get("min_score", 0) or 0)
    max_score = band.get("max_score")
    if max_score is None:
        return score >= min_score
    return min_score <= score <= int(max_score)


def assess_student_risk(registrations):
    """Score a student's filtered registrations and classify their current academic risk."""

    latest_registration = max(registrations, key=lambda registration: (registration.period.external_id, registration.id))
    mark_values = []
    failed_courses = 0
    total_modules = 0

    for registration in registrations:
        for result in registration.course_results.all():
            total_modules += 1
            if result.mark is None:
                continue
            mark_value = float(result.mark)
            mark_values.append(mark_value)
            if mark_value < 50:
                failed_courses += 1

    average_mark = round(sum(mark_values) / len(mark_values)) if mark_values else None
    carrying = max((registration.carrying or 0) for registration in registrations)
    decision_label = normalize_decision_label(latest_registration.decision)
    decision_key = decision_label.lower()

    risk_score = 0
    risk_drivers = []
    risk_driver_tags = []

    if average_mark is not None:
        if average_mark < 50:
            risk_score += 3
            risk_drivers.append("average below 50%")
            risk_driver_tags.append("average_below_50")
        elif average_mark < 60:
            risk_score += 1
            risk_drivers.append("average below 60%")
            risk_driver_tags.append("average_below_60")

    if failed_courses >= 3:
        risk_score += 3
        risk_drivers.append("3+ failed modules")
        risk_driver_tags.append("failed_3_plus")
    elif failed_courses == 2:
        risk_score += 2
        risk_drivers.append("2 failed modules")
        risk_driver_tags.append("failed_2")
    elif failed_courses == 1:
        risk_score += 1
        risk_drivers.append("1 failed module")
        risk_driver_tags.append("failed_1")

    if carrying >= 2:
        risk_score += 2
        risk_drivers.append(f"{carrying} carried modules")
        risk_driver_tags.append("carrying_multi")
    elif carrying == 1:
        risk_score += 1
        risk_drivers.append("1 carried module")
        risk_driver_tags.append("carrying_1")

    if decision_key in HIGH_RISK_DECISIONS:
        risk_score += 2
        risk_drivers.append(f"{decision_label} decision")
        risk_driver_tags.append("decision_alert")

    if risk_score >= 4:
        risk_level = "High Risk"
    elif risk_score >= 2:
        risk_level = "Medium Risk"
    else:
        risk_level = "Low Risk"

    return {
        "latest_registration": latest_registration,
        "average_mark": average_mark,
        "failed_courses": failed_courses,
        "total_modules": total_modules,
        "carrying": carrying,
        "risk_score": risk_score,
        "decision": decision_label,
        "risk_level": risk_level,
        "risk_level_key": risk_level.lower().replace(" ", "-"),
        "risk_driver_tags": risk_driver_tags,
        "risk_drivers": ", ".join(risk_drivers) if risk_drivers else "Performance currently stable",
    }


def build_student_risk_profiles_from_registrations(registrations):
    """Build per-student risk profiles from an already-filtered registration iterable."""

    student_registrations = {}
    for registration in registrations:
        student_registrations.setdefault(registration.student_id, []).append(registration)

    risk_rows = []
    for grouped_registrations in student_registrations.values():
        assessment = assess_student_risk(grouped_registrations)
        latest_registration = assessment["latest_registration"]
        department = latest_registration.programme.department if latest_registration.programme else None
        faculty = department.faculty if department else None
        academic_year_value = _safe_int(latest_registration.period.academic_year)
        semester_value = _safe_int(latest_registration.period.semester)
        risk_rows.append(
            {
                "name": latest_registration.student.full_name,
                "registration_number": latest_registration.student.registration_number,
                "programme": latest_registration.programme.normalized_name,
                "faculty": faculty.name if faculty else "Unassigned",
                "department": department.name if department else "Unassigned",
                "academic_level": format_academic_level_label(
                    latest_registration.period.academic_year,
                    latest_registration.period.semester,
                ),
                "academic_year_value": academic_year_value,
                "semester_value": semester_value,
                "average_mark": assessment["average_mark"] if assessment["average_mark"] is not None else "-",
                "average_mark_sort": assessment["average_mark"] if assessment["average_mark"] is not None else 999,
                "failed_courses": assessment["failed_courses"],
                "total_modules": assessment["total_modules"],
                "carrying": assessment["carrying"],
                "risk_score": assessment["risk_score"],
                "decision": assessment["decision"],
                "risk_level": assessment["risk_level"],
                "risk_level_key": assessment["risk_level_key"],
                "risk_driver_tags": assessment["risk_driver_tags"],
                "risk_drivers": assessment["risk_drivers"],
                "detail_slug": latest_registration.student.registration_number.lower(),
            }
        )

    def _student_name_sort_key(row):
        text = " ".join(str(row.get("name") or "").strip().split())
        if not text:
            return ("", "", str(row.get("registration_number") or "").lower())
        parts = text.split(" ")
        surname = parts[-1].lower()
        given_names = " ".join(parts[:-1]).lower()
        return (surname, given_names, str(row.get("registration_number") or "").lower())

    return sorted(risk_rows, key=_student_name_sort_key)


def build_student_risk_profiles(request, search_query=""):
    """Build per-student risk profiles from the currently filtered registration scope."""

    registrations = get_filtered_registrations(request)
    if search_query:
        registrations = registrations.filter(
            Q(student__first_names__icontains=search_query)
            | Q(student__surname__icontains=search_query)
            | Q(student__registration_number__icontains=search_query)
            | Q(programme__name__icontains=search_query)
            | Q(programme__department__name__icontains=search_query)
            | Q(decision__icontains=search_query)
        )

    return build_student_risk_profiles_from_registrations(list(registrations))


def format_risk_monitor_drivers(risk_driver_text):
    """Remove redundant phrases from the risk-monitor explanation shown on the table."""

    drivers = [driver.strip() for driver in str(risk_driver_text or "").split(",") if driver.strip()]
    filtered_drivers = [
        driver for driver in drivers
        if driver.lower() not in ["average below 50%", "3+ failed modules", "1 carried module", "repeat decision"]
    ]

    if filtered_drivers:
        return ", ".join(filtered_drivers)
    if drivers:
        return "Performance needs support"
    return "Performance currently stable"


def format_insight_flagged_meta(risk_driver_text, academic_level):
    """Build concise flagged-student copy for the insights page."""

    cleaned_driver_text = format_risk_monitor_drivers(risk_driver_text)
    lead_text = cleaned_driver_text.split(", ")[0] if cleaned_driver_text else "Performance needs support"

    if academic_level:
        return f"{lead_text} - {academic_level}"
    return lead_text


def build_risk_rows(request, search_query=""):
    """Build risk-monitor rows for students who need academic intervention."""

    risk_rows = []
    for row in build_student_risk_profiles(request, search_query):
        if row["risk_level"] == "Low Risk":
            continue

        risk_rows.append(
            {
                **row,
                "risk_drivers_display": format_risk_monitor_drivers(row["risk_drivers"]),
            }
        )

    return risk_rows


def _build_distribution_rows(risk_profiles):
    """Aggregate the visible cohort into the configured risk bands."""

    total_students = len(risk_profiles)
    distribution_rows = []
    for band in RISK_BAND_DEFINITIONS:
        count = sum(1 for row in risk_profiles if _match_band(int(row.get("risk_score", 0) or 0), band))
        distribution_rows.append(
            {
                "key": band["key"],
                "label": band["label"],
                "count": count,
                "share_pct": _format_share_pct(count, total_students),
                "tone": band["tone"],
            }
        )

    return distribution_rows


def _build_driver_rows(risk_rows):
    """Aggregate at-risk students by the drivers behind their watchlist status."""

    if not risk_rows:
        return []

    driver_counts = {}
    for row in risk_rows:
        for driver_tag in row.get("risk_driver_tags", []):
            driver_counts[driver_tag] = driver_counts.get(driver_tag, 0) + 1

    return [
        {
            "key": driver_key,
            "label": RISK_DRIVER_LABELS.get(driver_key, driver_key),
            "count": count,
            "share_pct": _format_share_pct(count, len(risk_rows)),
        }
        for driver_key, count in sorted(
            driver_counts.items(),
            key=lambda item: (
                -item[1],
                RISK_DRIVER_PRIORITY.get(item[0], 999),
                RISK_DRIVER_LABELS.get(item[0], item[0]),
            ),
        )
    ]


def _build_level_rows(risk_rows):
    """Aggregate at-risk students by academic level."""

    level_map = {}
    for row in risk_rows:
        level_key = row["academic_level"]
        entry = level_map.setdefault(
            level_key,
            {
                "level": level_key,
                "high_risk": 0,
                "medium_risk": 0,
                "total": 0,
                "share_pct": 0,
                "academic_year_value": row["academic_year_value"],
                "semester_value": row["semester_value"],
            },
        )
        entry["total"] += 1
        if row["risk_level"] == "High Risk":
            entry["high_risk"] += 1
        elif row["risk_level"] == "Medium Risk":
            entry["medium_risk"] += 1

    total_rows = len(risk_rows)
    level_rows = sorted(
        level_map.values(),
        key=lambda item: (-item["total"], -item["high_risk"], item["academic_year_value"], item["semester_value"], item["level"]),
    )
    for row in level_rows:
        row["share_pct"] = _format_share_pct(row["total"], total_rows)

    return level_rows


def _build_programme_rows(risk_rows):
    """Aggregate at-risk students by programme concentration."""

    programme_map = {}
    for row in risk_rows:
        programme_key = row["programme"]
        entry = programme_map.setdefault(
            programme_key,
            {
                "programme": programme_key,
                "faculty": row["faculty"],
                "high_risk": 0,
                "medium_risk": 0,
                "total": 0,
                "share_pct": 0,
            },
        )
        entry["total"] += 1
        if row["risk_level"] == "High Risk":
            entry["high_risk"] += 1
        elif row["risk_level"] == "Medium Risk":
            entry["medium_risk"] += 1

    total_rows = len(risk_rows)
    programme_rows = sorted(
        programme_map.values(),
        key=lambda item: (-item["total"], -item["high_risk"], item["programme"]),
    )[:10]
    for row in programme_rows:
        row["share_pct"] = _format_share_pct(row["total"], total_rows)

    return programme_rows


def build_risk_dashboard_data(request, search_query=""):
    """Build the risk story, charts, and action-register rows for the current filters."""

    risk_profiles = build_student_risk_profiles(request, search_query)
    risk_rows = [
        {
            **row,
            "risk_drivers_display": format_risk_monitor_drivers(row["risk_drivers"]),
        }
        for row in risk_profiles
        if row["risk_level"] != "Low Risk"
    ]

    distribution_rows = _build_distribution_rows(risk_profiles)
    driver_rows = _build_driver_rows(risk_rows)
    level_rows = _build_level_rows(risk_rows)
    programme_rows = _build_programme_rows(risk_rows)

    high_risk_count = sum(1 for row in risk_rows if row["risk_level"] == "High Risk")
    medium_risk_count = sum(1 for row in risk_rows if row["risk_level"] == "Medium Risk")
    critical_count = next(
        (row["count"] for row in distribution_rows if row["key"] == "critical"),
        0,
    )

    return {
        "risk_profiles": risk_profiles,
        "risk_rows": risk_rows,
        "total_students": len(risk_profiles),
        "at_risk_students": len(risk_rows),
        "watchlist_share_pct": _format_share_pct(len(risk_rows), len(risk_profiles)),
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "critical_count": critical_count,
        "multi_fail_count": sum(1 for row in risk_rows if row["failed_courses"] >= 2),
        "risk_distribution_rows": distribution_rows,
        "risk_driver_rows": driver_rows,
        "risk_level_rows": level_rows,
        "risk_programme_rows": programme_rows,
    }


def _build_risk_drilldown_rows(source_rows):
    """Normalise student rows for the modal drill-down table."""

    return [
        {
            "name": row["name"],
            "programme": row["programme"],
            "academic_level": row["academic_level"],
            "average_mark": row["average_mark"],
            "failed_courses": row["failed_courses"],
            "total_modules": row["total_modules"],
            "carrying": row["carrying"],
            "decision": row["decision"],
            "risk_level": row["risk_level"],
            "risk_level_key": row["risk_level_key"],
            "risk_drivers_display": format_risk_monitor_drivers(row["risk_drivers"]),
            "detail_url": f"/students/{row['detail_slug']}/",
        }
        for row in source_rows
    ]


def build_risk_drilldown_payload(request, chart_key, bucket_key, search_query="", page_number=None, page_size=10):
    """Build modal-ready drill-down payloads for risk charts."""

    risk_profiles = build_student_risk_profiles(request, search_query)
    risk_rows = [
        row
        for row in risk_profiles
        if row["risk_level"] != "Low Risk"
    ]

    normalized_chart = str(chart_key or "").strip().lower()
    normalized_bucket = str(bucket_key or "").strip()
    if not normalized_chart or not normalized_bucket:
        return None

    title = "Risk Drill-Down"
    subtitle = "No drill-down data is available for the current selection."
    matching_rows = []

    if normalized_chart == "distribution":
        band = next(
            (item for item in RISK_BAND_DEFINITIONS if item["key"] == normalized_bucket.lower()),
            None,
        )
        if not band:
            return None

        matching_rows = [
            row
            for row in risk_profiles
            if _match_band(int(row.get("risk_score", 0) or 0), band)
        ]
        band_label = RISK_DRILLDOWN_BAND_LABELS.get(band["key"], band["label"])
        title = f"{band_label} Students"
        subtitle = f"Students currently classified inside the {band_label.lower()} band for the selected scope."

    elif normalized_chart == "drivers":
        matching_rows = [
            row
            for row in risk_rows
            if normalized_bucket in row.get("risk_driver_tags", [])
        ]
        driver_label = RISK_DRIVER_LABELS.get(normalized_bucket, normalized_bucket.replace("_", " ").title())
        title = f"{driver_label} Students"
        subtitle = f"At-risk students currently linked to the {driver_label.lower()} driver."

    elif normalized_chart == "levels":
        matching_rows = [
            row
            for row in risk_rows
            if row["academic_level"] == normalized_bucket
        ]
        title = f"{normalized_bucket} Students"
        subtitle = f"At-risk students currently concentrated in {normalized_bucket}."

    elif normalized_chart == "programmes":
        matching_rows = [
            row
            for row in risk_rows
            if row["programme"] == normalized_bucket
        ]
        title = f"{normalized_bucket} Students"
        subtitle = f"At-risk students currently attached to {normalized_bucket}."

    elif normalized_chart == "programme_load":
        matching_rows = [
            row
            for row in risk_rows
            if row["programme"] == normalized_bucket
        ]
        title = f"{normalized_bucket} Students"
        subtitle = f"At-risk students currently attached to {normalized_bucket}."

    elif normalized_chart == "departments":
        matching_rows = [
            row
            for row in risk_rows
            if row["department"] == normalized_bucket
        ]
        title = f"{normalized_bucket} Students"
        subtitle = f"At-risk students currently attached to {normalized_bucket}."

    else:
        return None

    normalized_rows = _build_risk_drilldown_rows(matching_rows)
    paginated_rows = paginate_risk_rows(normalized_rows, page_number, page_size=page_size)
    return {
        "title": title,
        "subtitle": subtitle,
        "columns": list(RISK_DRILLDOWN_COLUMNS),
        **paginated_rows,
    }


def get_risk_summary_values(request, search_query=""):
    """Calculate student-risk summary metrics for asynchronous hydration."""

    risk_data = get_cached_risk_dashboard_data(request, search_query)
    return {
        "at_risk_students": risk_data["at_risk_students"],
        "high_risk": risk_data["high_risk_count"],
        "medium_risk": risk_data["medium_risk_count"],
        "multi_fail": risk_data["multi_fail_count"],
    }


def paginate_risk_rows(risk_rows, page_number, page_size=20):
    """Return the current register page plus pagination metadata for risk rows."""

    total_count = len(risk_rows)
    page_count = max(1, ((total_count - 1) // page_size) + 1) if total_count else 1

    try:
        page = int(page_number or 1)
    except (TypeError, ValueError):
        page = 1

    page = max(1, min(page, page_count))
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = risk_rows[start:end]
    page_window_start = max(page - 2, 1)
    page_window_end = min(page + 2, page_count)

    return {
        "rows": page_rows,
        "page": page,
        "page_size": page_size,
        "page_count": page_count,
        "page_numbers": list(range(page_window_start, page_window_end + 1)),
        "total_count": total_count,
        "start_index": start + 1 if total_count else 0,
        "end_index": min(end, total_count) if total_count else 0,
        "has_previous": page > 1,
        "has_next": page < page_count,
        "previous_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < page_count else None,
    }


def _build_risk_cache_key(request, suffix):
    """Create a stable cache key for the current risk filter scope."""

    query_string = urlencode(
        sorted((key, values) for key, values in request.GET.lists() if key != "page"),
        doseq=True,
    )
    return f"dashboard:risk:{suffix}:{query_string or 'all'}"


def get_cached_risk_dashboard_data(request, search_query=""):
    """Return cached risk analytics for the current filter scope."""

    cache_key = _build_risk_cache_key(request, "payload")
    return cache.get_or_set(
        cache_key,
        lambda: build_risk_dashboard_data(request, search_query),
        RISK_CACHE_TTL_SECONDS,
    )

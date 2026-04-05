"""Service-layer logic for the risk dashboard feature."""

from django.db.models import Q

from ..views import format_academic_level_label, get_filtered_registrations, normalize_decision_label
from .constants import (
    HIGH_RISK_DECISIONS,
    RISK_BAND_DEFINITIONS,
    RISK_DRIVER_LABELS,
    RISK_DRIVER_PRIORITY,
    RISK_PRIORITY,
)


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

    for registration in registrations:
        for result in registration.course_results.all():
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
        "carrying": carrying,
        "risk_score": risk_score,
        "decision": decision_label,
        "risk_level": risk_level,
        "risk_level_key": risk_level.lower().replace(" ", "-"),
        "risk_driver_tags": risk_driver_tags,
        "risk_drivers": ", ".join(risk_drivers) if risk_drivers else "Performance currently stable",
    }


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
                "programme": latest_registration.programme.name,
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

    return sorted(
        risk_rows,
        key=lambda row: (
            RISK_PRIORITY[row["risk_level"]],
            -row["risk_score"],
            -row["failed_courses"],
            row["average_mark_sort"],
            row["name"],
        ),
    )


def format_risk_monitor_drivers(risk_driver_text):
    """Remove redundant phrases from the risk-monitor explanation shown on the table."""

    drivers = [driver.strip() for driver in str(risk_driver_text or "").split(",") if driver.strip()]
    filtered_drivers = [driver for driver in drivers if driver.lower() != "average below 50%"]

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


def get_risk_summary_values(request, search_query=""):
    """Calculate student-risk summary metrics for asynchronous hydration."""

    risk_data = build_risk_dashboard_data(request, search_query)
    return {
        "at_risk_students": risk_data["at_risk_students"],
        "high_risk": risk_data["high_risk_count"],
        "medium_risk": risk_data["medium_risk_count"],
        "multi_fail": risk_data["multi_fail_count"],
    }

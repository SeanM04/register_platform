"""Service-layer logic for the institutional insights dashboard."""

from urllib.parse import urlencode

from django.core.cache import cache
from django.urls import reverse

from ..risk.constants import RISK_DRIVER_LABELS, RISK_DRIVER_PRIORITY
from ..risk.services import build_student_risk_profiles, format_insight_flagged_meta
from ..views import RETENTION_EXIT_DECISIONS, build_initials, get_filtered_registrations

INSIGHTS_CACHE_TTL_SECONDS = 30


def _pct(count, total):
    """Return a rounded percentage while safely handling empty totals."""

    return round((count / total) * 100) if total else 0


def _get_registration_faculty_name(registration):
    """Return the registration faculty label used on charts and cards."""

    department = registration.programme.department if registration.programme else None
    faculty = department.faculty if department else None
    return faculty.name if faculty else "Unassigned"


def build_insight_scope_pills(request):
    """Build compact scope pills summarising the current insights filter state."""

    selected_faculty = request.GET.get("faculty", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_year = request.GET.get("year", "").strip()

    pills = [
        {
            "label": "Filtered scope" if any([selected_faculty, selected_period, selected_year]) else "Live analysis",
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


def _build_summary_cards(total_students, total_registrations, at_risk_profiles, high_risk_profiles, medium_risk_profiles, retention_rate, retained_students, top_faculty_name, faculty_load_pct):
    """Build the executive summary cards shown at the top of the insights page."""

    return [
        {
            "label": "At-Risk Students",
            "value": f"{len(at_risk_profiles):,}",
            "note": f"{len(high_risk_profiles)} high priority",
            "tone": "danger",
        },
        {
            "label": "High Priority",
            "value": f"{len(high_risk_profiles):,}",
            "note": f"{len(medium_risk_profiles)} medium priority",
            "tone": "warning",
        },
        {
            "label": "Retention Rate",
            "value": f"{retention_rate}%",
            "note": f"{retained_students:,} students persisting",
            "tone": "neutral",
        },
        {
            "label": "Active Cohort",
            "value": f"{total_students}",
            "note": (
                f"{top_faculty_name} carries {faculty_load_pct}% of registrations"
                if total_registrations
                else "Registration load data is not available yet"
            ),
            "tone": "success",
        },
    ]


def _build_flagged_students(at_risk_profiles):
    """Build the compact action queue shown near the end of the page."""

    flagged_students = []
    for row in at_risk_profiles[:5]:
        flagged_students.append(
            {
                "initials": build_initials(row["name"]),
                "name": row["name"],
                "meta": format_insight_flagged_meta(row["risk_drivers"], row["academic_level"]),
                "risk_level": row["risk_level"],
                "risk_key": row["risk_level_key"],
                "detail_slug": row["detail_slug"],
            }
        )

    return flagged_students


def _build_faculty_load_rows(registrations):
    """Aggregate registration load by faculty for the executive load chart."""

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


def _build_risk_distribution_rows(risk_profiles):
    """Aggregate the visible cohort into broad risk bands for the headline chart."""

    total_students = len(risk_profiles)
    risk_bands = [
    ("low", "Low (0-1)", lambda score: score <= 1, "low"),
    ("moderate", "Moderate (2-3)", lambda score: 2 <= score <= 3, "moderate"),
    ("high", "High (4-5)", lambda score: 4 <= score <= 5, "high"),
    ("critical", "Critical (6+)", lambda score: score >= 6, "critical"),
]

    rows = []
    for key, label, matcher, tone in risk_bands:
        count = sum(1 for row in risk_profiles if matcher(int(row.get("risk_score", 0) or 0)))
        rows.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "percent": _pct(count, total_students),
                "tone": tone,
            }
        )

    return rows


def _build_driver_rows(at_risk_profiles):
    """Aggregate the recurring risk drivers across the active watchlist."""

    driver_counts = {}
    for row in at_risk_profiles:
        for driver_tag in row.get("risk_driver_tags", []):
            driver_counts[driver_tag] = driver_counts.get(driver_tag, 0) + 1

    rows = [
        {
            "key": driver_key,
            "label": RISK_DRIVER_LABELS.get(driver_key, driver_key),
            "count": count,
            "share_pct": _pct(count, len(at_risk_profiles)),
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

    return rows[:6]


def _build_faculty_pressure_rows(at_risk_profiles):
    """Aggregate the at-risk cohort by faculty and severity mix."""

    faculty_map = {}
    for row in at_risk_profiles:
        entry = faculty_map.setdefault(
            row["faculty"],
            {
                "label": row["faculty"],
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

    rows = sorted(
        faculty_map.values(),
        key=lambda item: (-item["total"], -item["high_risk"], item["label"]),
    )
    total_flagged = len(at_risk_profiles)
    for row in rows:
        row["share_pct"] = _pct(row["total"], total_flagged)
    return rows[:6]


def _build_confidence_rows(total_students, retention_rate, at_risk_profiles, faculty_load_rows):
    """Build lightweight confidence bars for the action chapter."""

    sample_size_factor = min(14, total_students // 35)
    high_signal_factor = min(10, sum(1 for row in at_risk_profiles if row["risk_level"] == "High Risk") * 2)
    lead_faculty_share = faculty_load_rows[0]["share_pct"] if faculty_load_rows else 0
    concentration_factor = 8 if lead_faculty_share >= 45 else 4

    return [
        {
            "label": "Student flagging",
            "value": min(96, 78 + sample_size_factor + high_signal_factor),
        },
        {
            "label": "Retention outlook",
            "value": min(95, 74 + sample_size_factor + (4 if retention_rate >= 80 else 1)),
        },
        {
            "label": "Faculty balancing",
            "value": min(93, 70 + sample_size_factor + concentration_factor),
        },
        {
            "label": "Intervention targeting",
            "value": min(97, 76 + sample_size_factor + (6 if at_risk_profiles else 0)),
        },
    ]


def _build_recommendations(high_risk_profiles, faculty_load_rows, faculty_pressure_rows, driver_rows):
    """Build deterministic action cards from the strongest live signals."""

    lead_faculty = faculty_load_rows[0] if faculty_load_rows else None
    lead_pressure = faculty_pressure_rows[0] if faculty_pressure_rows else None
    lead_driver = driver_rows[0] if driver_rows else None

    return [
        {
            "title": "Escalate high-risk advising",
            "description": (
                f"{len(high_risk_profiles)} students are already in the high-risk band. Prioritise advisor outreach and follow-up case reviews in the next intervention cycle."
                if high_risk_profiles
                else "No students are currently in the high-risk band. Keep the weekly watchlist review active so medium-risk cases do not harden into urgent interventions."
            ),
            "priority": "High priority" if high_risk_profiles else "Monitor",
            "priority_key": "high" if high_risk_profiles else "neutral",
            "action_label": "Open risk register",
            "action_url": reverse("dashboard:risk"),
        },
        {
            "title": "Balance support capacity",
            "description": (
                f"{lead_faculty['label']} holds {lead_faculty['share_pct']}% of registrations in scope, while {lead_pressure['label']} carries {lead_pressure['share_pct']}% of flagged students."
                if lead_faculty and lead_pressure
                else "Faculty concentration is light in the current scope. Keep support staffing broadly distributed until stronger clusters appear."
            ),
            "priority": "High priority" if lead_faculty and lead_faculty["share_pct"] >= 45 else "Medium priority",
            "priority_key": "high" if lead_faculty and lead_faculty["share_pct"] >= 45 else "medium",
            "action_label": "Review demographics",
            "action_url": reverse("dashboard:demographic"),
        },
        {
            "title": "Tackle the lead driver",
            "description": (
                f"{lead_driver['label']} currently appears in {lead_driver['count']} flagged students. Build the next support touchpoint around that recurring pressure."
                if lead_driver
                else "Recurring intervention drivers are not concentrated in the current filters. Keep support case-by-case until a dominant pattern emerges."
            ),
            "priority": "Medium priority",
            "priority_key": "medium",
            "action_label": "Open academic levels",
            "action_url": reverse("dashboard:academic-level"),
        },
    ]


def build_insights_dashboard_data(request):
    """Assemble the story, chart, and action data for the institutional insights page."""

    registrations = list(get_filtered_registrations(request))
    total_registrations = len(registrations)
    risk_profiles = build_student_risk_profiles(request)
    at_risk_profiles = [row for row in risk_profiles if row["risk_level"] != "Low Risk"]
    high_risk_profiles = [row for row in at_risk_profiles if row["risk_level"] == "High Risk"]
    medium_risk_profiles = [row for row in at_risk_profiles if row["risk_level"] == "Medium Risk"]
    total_students = len(risk_profiles)

    retained_students = sum(
        1 for row in risk_profiles if row["decision"].lower() not in RETENTION_EXIT_DECISIONS
    )
    retention_rate = _pct(retained_students, total_students)

    faculty_load_rows = _build_faculty_load_rows(registrations)
    top_faculty_name = faculty_load_rows[0]["label"] if faculty_load_rows else "No faculty data"
    faculty_load_pct = faculty_load_rows[0]["share_pct"] if faculty_load_rows else 0

    risk_distribution_rows = _build_risk_distribution_rows(risk_profiles)
    driver_rows = _build_driver_rows(at_risk_profiles)
    faculty_pressure_rows = _build_faculty_pressure_rows(at_risk_profiles)
    confidence_rows = _build_confidence_rows(total_students, retention_rate, at_risk_profiles, faculty_load_rows)
    recommendations = _build_recommendations(
        high_risk_profiles,
        faculty_load_rows,
        faculty_pressure_rows,
        driver_rows,
    )

    return {
        "summary_cards": _build_summary_cards(
            total_students,
            total_registrations,
            at_risk_profiles,
            high_risk_profiles,
            medium_risk_profiles,
            retention_rate,
            retained_students,
            top_faculty_name,
            faculty_load_pct,
        ),
        "scope_pills": build_insight_scope_pills(request),
        "flagged_students": _build_flagged_students(at_risk_profiles),
        "flagged_total": len(at_risk_profiles),
        "recommendations": recommendations,
        "faculty_load_rows": faculty_load_rows,
        "risk_distribution_rows": risk_distribution_rows,
        "faculty_pressure_rows": faculty_pressure_rows,
        "driver_rows": driver_rows,
        "confidence_rows": confidence_rows,
        "total_students": total_students,
        "total_registrations": total_registrations,
        "retention_rate": retention_rate,
        "retained_students": retained_students,
        "high_risk_total": len(high_risk_profiles),
        "medium_risk_total": len(medium_risk_profiles),
        "watchlist_share_pct": _pct(len(at_risk_profiles), total_students),
    }


def _build_insights_cache_key(request):
    """Create a stable cache key for the current insights filter scope."""

    query_string = urlencode(sorted(request.GET.lists()), doseq=True)
    return f"dashboard:insights:{query_string or 'all'}"


def get_cached_insights_dashboard_data(request):
    """Return cached insights analytics for the current filter scope."""

    cache_key = _build_insights_cache_key(request)
    return cache.get_or_set(
        cache_key,
        lambda: build_insights_dashboard_data(request),
        INSIGHTS_CACHE_TTL_SECONDS,
    )


# Drilldown functionality for insights
INSIGHTS_DRILLDOWN_COLUMNS = (
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


def _match_band(score, band):
    """Check whether a numeric risk score belongs to a configured band."""
    min_score = int(band.get("min_score", 0) or 0)
    max_score = band.get("max_score")
    if max_score is None:
        return score >= min_score
    return min_score <= score <= int(max_score)


def build_hierarchical_drilldown_data(request, chart_key, bucket_key, search_query=""):
    """Build hierarchical drilldown data for faculty load (faculty → department → programme → students)."""
    
    risk_profiles = build_student_risk_profiles(request, search_query)
    
    if chart_key == "faculty_load" or chart_key == "faculty_pressure":
        # Return departments for a faculty
        # For faculty_pressure, only include at-risk students
        departments = {}
        for row in risk_profiles:
            if row.get("faculty", "").lower() == bucket_key.lower():
                # For faculty_pressure, only count at-risk students
                if chart_key == "faculty_pressure" and row.get("risk_level") == "Low Risk":
                    continue
                    
                dept = row.get("department", "Unassigned")
                if dept not in departments:
                    departments[dept] = {
                        "name": dept,
                        "student_count": 0,
                        "programmes": set()
                    }
                departments[dept]["student_count"] += 1
                departments[dept]["programmes"].add(row.get("programme", ""))
        
        title_suffix = "At-Risk Students" if chart_key == "faculty_pressure" else "Departments"
        return {
            "type": "departments",
            "title": f"{bucket_key} - {title_suffix}",
            "subtitle": f"At-risk departments within {bucket_key} faculty" if chart_key == "faculty_pressure" else f"Departments within {bucket_key} faculty",
            "data": [
                {
                    "label": dept_name,
                    "count": dept_data["student_count"],
                    "programme_count": len(dept_data["programmes"])
                }
                for dept_name, dept_data in departments.items()
                if dept_name != "Unassigned"
            ]
        }
    
    elif chart_key == "faculty_department":
        # Return programmes for a department
        programmes = {}
        for row in risk_profiles:
            if (row.get("faculty", "").lower() == bucket_key.split("|")[0].lower() and 
                row.get("department", "").lower() == bucket_key.split("|")[1].lower()):
                prog = row.get("programme", "")
                if prog not in programmes:
                    programmes[prog] = 0
                programmes[prog] += 1
        
        return {
            "type": "programmes", 
            "title": f"{bucket_key.split('|')[1]} - Programmes",
            "subtitle": f"Programmes within {bucket_key.split('|')[1]} department",
            "data": [
                {
                    "label": prog_name,
                    "count": student_count
                }
                for prog_name, student_count in programmes.items()
                if prog_name
            ]
        }
    
    return None


def build_insights_drilldown_payload(request, chart_key, bucket_key, search_query="", page_number=None, page_size=10):
    """Build modal-ready drill-down payloads for insights charts."""

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

    title = "Insights Drill-Down"
    subtitle = "No drill-down data is available for the current selection."
    matching_rows = []

    if normalized_chart == "risk_distribution":
        # Handle risk band drilldown similar to risk page
        from ..risk.constants import RISK_BAND_DEFINITIONS
        from ..risk.services import RISK_DRILLDOWN_BAND_LABELS

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

    elif normalized_chart == "faculty_pressure":
        # Handle faculty pressure drilldown
        matching_rows = [
            row
            for row in risk_profiles
            if row.get("faculty", "").lower() == normalized_bucket.lower()
        ]
        faculty_label = normalized_bucket.replace("_", " ").title()
        title = f"{faculty_label} Students"
        subtitle = f"At-risk students currently in the {faculty_label.lower()} faculty."

    elif normalized_chart == "drivers":
        # Handle risk drivers drilldown
        matching_rows = [
            row
            for row in risk_rows
            if normalized_bucket in row.get("risk_driver_tags", [])
        ]
        driver_label = RISK_DRIVER_LABELS.get(normalized_bucket, normalized_bucket.replace("_", " ").title())
        title = f"{driver_label} Students"
        subtitle = f"At-risk students currently linked to the {driver_label.lower()} driver."

    elif normalized_chart == "faculty_load":
        # Handle faculty load drilldown
        matching_rows = [
            row
            for row in risk_profiles
            if row.get("faculty", "").lower() == normalized_bucket.lower()
        ]
        faculty_label = normalized_bucket.replace("_", " ").title()
        title = f"{faculty_label} Students"
        subtitle = f"Students currently enrolled in the {faculty_label.lower()} faculty."

    elif normalized_chart == "faculty_pressure":
        # Handle faculty pressure drilldown (at-risk students only)
        matching_rows = [
            row
            for row in risk_profiles
            if (row.get("faculty", "").lower() == normalized_bucket.lower() and 
                row.get("risk_level") != "Low Risk")
        ]
        faculty_label = normalized_bucket.replace("_", " ").title()
        title = f"{faculty_label} - At-Risk Students"
        subtitle = f"At-risk students currently enrolled in the {faculty_label.lower()} faculty."

    elif normalized_chart == "faculty_department":
        # Handle department drilldown from faculty hierarchy
        faculty_name, department_name = normalized_bucket.split("|", 1)
        matching_rows = [
            row
            for row in risk_profiles
            if (row.get("faculty", "").lower() == faculty_name.lower() and 
                row.get("department", "").lower() == department_name.lower())
        ]
        department_label = department_name.replace("_", " ").title()
        title = f"{department_label} - Programmes"
        subtitle = f"Programmes within the {department_label.lower()} department."

    elif normalized_chart == "faculty_programme":
        # Handle programme drilldown from faculty hierarchy
        matching_rows = [
            row
            for row in risk_profiles
            if row.get("programme", "").lower() == normalized_bucket.lower()
        ]
        programme_label = normalized_bucket.replace("_", " ").title()
        title = f"{programme_label} Students"
        subtitle = f"Students currently enrolled in the {programme_label.lower()} programme."

    else:
        return None

    # Normalize and paginate results
    from ..risk.services import _build_risk_drilldown_rows, paginate_risk_rows
    normalized_rows = _build_risk_drilldown_rows(matching_rows)
    paginated_rows = paginate_risk_rows(normalized_rows, page_number or 1, page_size=page_size)
    
    return {
        "title": title,
        "subtitle": subtitle,
        "columns": list(INSIGHTS_DRILLDOWN_COLUMNS),
        **paginated_rows,
    }

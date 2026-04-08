"""Service-layer logic for the story-first landing dashboard."""

from collections import Counter

from django.db.models import Avg
from django.urls import reverse

from ..models import CourseResult
from ..risk.services import build_student_risk_profiles
from ..views import RETENTION_EXIT_DECISIONS, get_filtered_registrations, normalize_decision_label, normalize_gender_key
from .constants import OVERVIEW_SUMMARY_CARD_SPECS, PROGRESS_STATUS_CONFIG, RISK_BAND_CONFIG


def _calculate_first_year_retention(registrations):
    """Calculate First Year Retention rate based on student progression."""
    
    # Debug: Show what semester values actually exist
    semester_values = []
    for registration in registrations:
        if registration.period and registration.period.semester:
            semester_values.append(str(registration.period.semester))
    
    unique_semesters = list(set(semester_values))
    print(f"DEBUG: Semester values in data: {unique_semesters}")
    print(f"DEBUG: Total registrations: {len(registrations)}")
    
    # Get students in their first year (semester 1 registrations)
    first_year_students = set()
    for registration in registrations:
        semester_value = registration.period.semester
        
        # Handle various semester representations - check for first semester
        if semester_value is not None:
            semester_str = str(semester_value).strip().lower()
            # Match first semester variations: "1", "first", "semester 1", "first year", etc.
            if (semester_str == "1" or 
                semester_str.startswith("1") or 
                semester_str.startswith("first") or 
                "semester 1" in semester_str or
                "first year" in semester_str):
                first_year_students.add(registration.student_id)
    
    print(f"DEBUG: Found {len(first_year_students)} first-year students")
    
    if not first_year_students:
        return "0%"
    
    # Count how many of these first year students have subsequent registrations
    retained_students = 0
    for student_id in first_year_students:
        student_registrations = [r for r in registrations if r.student_id == student_id]
        # Check if student has registrations beyond first semester
        has_subsequent = any(
            r.period.semester is not None and 
            str(r.period.semester).strip().lower() not in ["1", ""] and
            not str(r.period.semester).strip().lower().startswith("1") and
            not "first" in str(r.period.semester).strip().lower()
            for r in student_registrations
        )
        if has_subsequent:
            retained_students += 1
    
    retention_rate = _pct(retained_students, len(first_year_students))
    return f"{retention_rate}%"


def _calculate_students_satisfaction(marked_results):
    """Calculate Students Satisfaction based on performance metrics."""
    
    if not marked_results.exists():
        return "0%"
    
    # Calculate satisfaction based on:
    # - Percentage of students with marks above 60%
    # - Average mark performance
    total_results = marked_results.count()
    high_performers = marked_results.filter(mark__gte=60).count()
    average_mark = marked_results.aggregate(value=Avg("mark"))["value"] or 0
    
    # Weight the satisfaction score
    performance_score = _pct(high_performers, total_results)
    average_score = min(100, round((average_mark / 100) * 100))
    
    # Combine both metrics (70% weight to performance, 30% to average)
    satisfaction_score = round((performance_score * 0.7) + (average_score * 0.3))
    return f"{satisfaction_score}%"


def _pct(count, total):
    """Return a rounded percentage while safely handling empty totals."""

    return round((count / total) * 100) if total else 0


def _format_count(value):
    """Format integers with grouping for short note copy."""

    return f"{int(value or 0):,}"


def _get_results_queryset(registrations):
    """Return course results tied to the currently filtered registrations."""

    registration_ids = [registration.id for registration in registrations]
    if not registration_ids:
        return CourseResult.objects.none()
    return CourseResult.objects.filter(registration_id__in=registration_ids)


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


def _build_summary_values(registrations, marked_results, risk_profiles):
    """Calculate the headline KPI values shown on the landing page."""

    total_registered = len(registrations)
    total_students = len({registration.student_id for registration in registrations})
    result_count = marked_results.count()
    pass_count = marked_results.filter(mark__gte=50).count()
    average_mark = marked_results.aggregate(value=Avg("mark"))["value"]
    proceed_count = sum(1 for registration in registrations if str(registration.decision or "").strip().lower().startswith("proceed"))
    on_time_count = sum(
        1
        for registration in registrations
        if str(registration.decision or "").strip().lower() == "proceed" and (registration.carrying == 0)
    )
    first_semester_count = sum(1 for registration in registrations if str(registration.period.semester or "").strip() == "1")
    at_risk_count = sum(1 for row in risk_profiles if row["risk_level"] != "Low Risk")
    
    # Calculate First Year Retention
    first_year_retention = _calculate_first_year_retention(registrations)
    
    # Calculate Students Satisfaction (using average marks as proxy)
    students_satisfaction = _calculate_students_satisfaction(marked_results)

    return {
        "enrolled": total_students,
        "registered": total_registered,
        "pass_rate": f"{round((pass_count / result_count) * 100)}%" if result_count else "0%",
        "completion_rate": proceed_count,
        "on_time_graduation": on_time_count,
        "first_year_retention": first_year_retention,
        "students_satisfaction": students_satisfaction,
        "average_mark": round(average_mark or 0),
        "first_semester": first_semester_count,
        "at_risk": at_risk_count,
    }


def _build_summary_cards(summary_values, faculty_load_rows, marked_results, risk_profiles):
    """Build the executive summary cards shown at the top of the landing page."""

    high_risk_count = sum(1 for row in risk_profiles if row["risk_level"] == "High Risk")
    medium_risk_count = sum(1 for row in risk_profiles if row["risk_level"] == "Medium Risk")
    pass_count = marked_results.filter(mark__gte=50).count()
    result_count = marked_results.count()
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
            else "No are currently in medium or high-risk bands."
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


def _build_outcome_rows(results):
    """Aggregate visible assessment outcomes for the first landing-page chart."""

    total_results = results.count()
    rows = [
        {
            "key": "passed",
            "label": "Passed",
            "count": results.filter(mark__gte=50).count(),
            "percent": 0,
            "tone": "success",
        },
        {
            "key": "failed",
            "label": "Failed",
            "count": results.filter(mark__lt=50).count(),
            "percent": 0,
            "tone": "danger",
        },
        {
            "key": "awaiting",
            "label": "Awaiting Mark",
            "count": results.filter(mark__isnull=True).count(),
            "percent": 0,
            "tone": "neutral",
        },
    ]

    filtered_rows = [row for row in rows if row["count"] > 0]
    for row in filtered_rows:
        row["percent"] = _pct(row["count"], total_results)
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

    registrations = list(get_filtered_registrations(request))
    results = _get_results_queryset(registrations).exclude(mark__isnull=True)
    risk_profiles = build_student_risk_profiles(request)
    return _build_summary_values(registrations, results, risk_profiles)


def build_overview_dashboard_data(request):
    """Assemble the real landing-page signals shown immediately after login."""

    registrations = list(get_filtered_registrations(request))
    results = _get_results_queryset(registrations)
    marked_results = results.exclude(mark__isnull=True)
    risk_profiles = build_student_risk_profiles(request)
    faculty_load_rows = _build_faculty_load_rows(registrations)
    students = _build_student_snapshot(registrations)
    gender_rows = _build_gender_rows(students)
    location_rows = _build_birth_location_rows(students)
    summary_values = _build_summary_values(registrations, marked_results, risk_profiles)

    return {
        "summary_cards": _build_summary_cards(summary_values, faculty_load_rows, marked_results, risk_profiles),
        "scope_pills": build_overview_scope_pills(request),
        "outcome_rows": _build_outcome_rows(results),
        "risk_distribution_rows": _build_risk_distribution_rows(risk_profiles),
        "faculty_load_rows": faculty_load_rows,
        "progress_rows": _build_progress_rows(registrations),
        "action_cards": _build_action_cards(risk_profiles, faculty_load_rows, gender_rows, location_rows),
    }

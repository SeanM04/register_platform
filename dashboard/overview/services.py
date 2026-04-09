"""Service-layer logic for the story-first landing dashboard."""

from collections import Counter
from urllib.parse import urlencode

from django.core.cache import cache
from django.urls import reverse

from ..risk.services import build_student_risk_profiles_from_registrations
from ..views import RETENTION_EXIT_DECISIONS, get_filtered_registrations, normalize_decision_label, normalize_gender_key
from .constants import OVERVIEW_SUMMARY_CARD_SPECS, PROGRESS_STATUS_CONFIG, RISK_BAND_CONFIG

OVERVIEW_CACHE_TTL_SECONDS = 30


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

    # Basic debug to see if function is called
    print(f"DEBUG: _calculate_first_year_retention called with {len(registrations)} registrations")
    
    if not registrations:
        print("DEBUG: No registrations provided")
        return "No data available"

    # Group registrations by student to track their progression
    student_records = {}
    academic_years_found = set()
    semesters_found = set()
    period_details = []
    
    for registration in registrations:
        student_id = registration.student_id
        
        # Use stored academic year and semester from AcademicPeriod model
        academic_year = None
        semester = None
        
        if registration.period:
            # Use the stored academic_year and semester fields from AcademicPeriod
            try:
                academic_year = int(registration.period.academic_year) if registration.period.academic_year else None
                semester = int(registration.period.semester) if registration.period.semester else None
            except (ValueError, TypeError):
                academic_year = None
                semester = None
        
        period_name = registration.period.name.lower() if registration.period else ""
        
        # Track what years and semesters we're finding
        if academic_year is not None:
            academic_years_found.add(academic_year)
        if semester is not None:
            semesters_found.add(semester)
        
        # Collect period details for debugging
        period_details.append({
            'period_name': period_name,
            'stored_academic_year': registration.period.academic_year if registration.period else None,
            'stored_semester': registration.period.semester if registration.period else None,
            'extracted_academic_year': academic_year,
            'extracted_semester': semester,
            'student_id': student_id
        })
        
        # Store student's academic record
        if student_id not in student_records:
            student_records[student_id] = {
                'faculty': _get_registration_faculty_name(registration),
                'records': []
            }
        
        student_records[student_id]['records'].append({
            'academic_year': academic_year,
            'semester': semester,
            'period_name': period_name
        })

    # Debug: Log comprehensive information
    print(f"DEBUG: Academic years found: {sorted(academic_years_found)}")
    print(f"DEBUG: Semesters found: {sorted(semesters_found)}")
    print(f"DEBUG: Total students processed: {len(student_records)}")
    print(f"DEBUG: Total registrations processed: {len(period_details)}")
    
    # Show sample period details
    print(f"DEBUG: Sample period details:")
    for i, detail in enumerate(period_details[:5]):  # Show first 5
        print(f"  {i+1}. Period: '{detail['period_name']}' -> Stored: Year {detail['stored_academic_year']}, Sem {detail['stored_semester']} -> Extracted: Year {detail['extracted_academic_year']}, Sem {detail['extracted_semester']} (Student {detail['student_id']})")
    
    # Count students by academic year and semester
    year_semester_counts = {}
    for student_id, data in student_records.items():
        for record in data['records']:
            if record['academic_year'] is not None and record['semester'] is not None:
                key = (record['academic_year'], record['semester'])
                year_semester_counts[key] = year_semester_counts.get(key, 0) + 1
    
    print(f"DEBUG: Students by Year/Semester:")
    for (year, semester), count in sorted(year_semester_counts.items()):
        print(f"  Year {year}, Semester {semester}: {count} students")

    # CORRECT APPROACH: First-year students are those without previous registrations
    # These are the new students who enroll as Academic Year 1, Semester 1 in each period
    
    # Get all student IDs from the filtered registrations
    filtered_student_ids = set(student_records.keys())
    
    # Check each student's complete registration history to determine if they're first-year
    first_year_students = []
    
    for student_id in filtered_student_ids:
        # Get all registrations for this student (not just filtered ones)
        from dashboard.models import Registration
        all_student_regs = Registration.objects.filter(student_id=student_id).order_by('created_at')
        
        # Check if this student's first registration is within the filtered periods
        first_reg = all_student_regs.first()
        if first_reg and first_reg.period_id in [reg.period_id for reg in registrations if reg.student_id == student_id]:
            # This student's first registration is in the filtered data - they are first-year students
            first_year_students.append({
                'student_id': student_id,
                'faculty': student_records[student_id]['faculty'],
                'records': student_records[student_id]['records']
            })

    print(f"DEBUG: First-year students (new enrollments in filtered periods) found: {len(first_year_students)}")

    if not first_year_students:
        print("DEBUG: No first-year students found in filtered data")
        return "No data available"

    # Check progression for each first-year student
    progressed_students = 0
    for student in first_year_students:
        # A student progresses if they have more than 1 registration total
        # This means they continued beyond their first period
        
        from dashboard.models import Registration
        total_registrations = Registration.objects.filter(student_id=student['student_id']).count()
        
        if total_registrations > 1:
            progressed_students += 1

    print(f"DEBUG: Progressed students: {progressed_students} out of {len(first_year_students)}")

    # Calculate retention rate
    retention_rate = _pct(progressed_students, len(first_year_students))
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

    # Calculate student-level outcomes instead of course-level
    student_outcomes = {}  # Track each student's overall outcome
    
    for registration in registrations:
        student_id = registration.student_id
        if student_id in student_outcomes:
            continue  # Already processed this student
            
        student_results = list(registration.course_results.all())
        if not student_results:
            continue  # No results for this student
            
        summary["total_count"] += 1
        
        # Calculate student's average mark across all courses
        marked_results = [r for r in student_results if r.mark is not None]
        awaiting_results = [r for r in student_results if r.mark is None]
        
        if not marked_results and awaiting_results:
            # Student has results but none marked yet
            summary["awaiting_count"] += 1
            student_outcomes[student_id] = "awaiting"
            continue
            
        if not marked_results:
            # No marked results for this student
            continue
            
        # Calculate student's average mark
        student_avg = sum(float(r.mark) for r in marked_results) / len(marked_results)
        total_mark_sum += student_avg
        summary["marked_count"] += 1
        
        # Determine student outcome based on average
        if student_avg >= 50:
            summary["pass_count"] += 1
            student_outcomes[student_id] = "passed"
        else:
            summary["fail_count"] += 1
            student_outcomes[student_id] = "failed"
            
        if student_avg >= 60:
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
    cached_payload = cache.get(cache_key)
    if cached_payload is not None:
        return cached_payload

    overview_data = build_overview_dashboard_data(request)
    cache.set(cache_key, overview_data, OVERVIEW_CACHE_TTL_SECONDS)
    return overview_data

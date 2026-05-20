"""Shared student academic history helpers."""

from collections import defaultdict
import re


PASS_MARK = 50


def _registration_results(registration):
    """Return course results, preferring prefetched results when present."""

    prefetched_results = getattr(registration, "prefetched_course_results", None)
    if prefetched_results is not None:
        return prefetched_results
    return registration.course_results.all()


def _coerce_int(value, default=None):
    """Return the first integer found in a value."""

    if value is None:
        return default
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return default
    if text.isdigit():
        return int(text)

    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    return default


def extract_registration_year_semester(registration):
    """Resolve the canonical programme year and semester for a registration."""

    period = getattr(registration, "period", None)
    year = _coerce_int(getattr(period, "academic_year", None))
    semester = _coerce_int(getattr(period, "semester", None))
    period_name = str(getattr(period, "name", "") or "")

    if year is None:
        year_match = re.search(r"\byear\s*(\d+)\b", period_name, flags=re.IGNORECASE)
        year = int(year_match.group(1)) if year_match else 1

    if semester is None:
        semester_match = re.search(r"\b(?:semester|sem|term)\s*(\d+)\b", period_name, flags=re.IGNORECASE)
        semester = int(semester_match.group(1)) if semester_match else 1

    return max(year or 1, 1), max(semester or 1, 1)


def format_year_label(year):
    return f"Year {int(year)}"


def format_semester_label(semester):
    return f"Semester {int(semester)}"


def format_academic_level_label(year, semester):
    return f"{format_year_label(year)} {format_semester_label(semester)}"


def build_registration_group_key(registration):
    """Return a stable programme-structure key for a registration."""

    year, semester = extract_registration_year_semester(registration)
    return f"{year}:{semester}"


def sort_registrations_by_structure(registrations):
    """Sort registrations by programme structure instead of raw attempt count."""

    return sorted(
        registrations,
        key=lambda registration: (
            *extract_registration_year_semester(registration),
            getattr(getattr(registration, "period", None), "external_id", 0) or 0,
            registration.id or 0,
        ),
    )


def _registration_course_codes(registration):
    """Return normalized course codes attached to a registration."""

    codes = []
    for result in _registration_results(registration):
        course = getattr(result, "course", None)
        code = str(getattr(course, "code", "") or "").strip()
        if code:
            codes.append(code)
    return codes


def _should_merge_with_group(group, year, semester, registration_course_codes):
    """Decide whether a registration continues the current displayed semester."""

    if group["raw_year"] != year or group["raw_semester"] != semester:
        return False

    if not registration_course_codes:
        return True

    existing_codes = group["course_codes"]
    if not existing_codes:
        return False

    overlap = sum(1 for code in registration_course_codes if code in existing_codes)
    overlap_ratio = overlap / len(registration_course_codes)
    return overlap_ratio >= 0.5


def build_student_timeline(registrations):
    """
    Build a structure-based academic timeline.

    Repeated registrations in the same official year/semester collapse into one
    semester container, while every course attempt remains visible for audit and
    transcript history.
    """

    ordered_registrations = sort_registrations_by_structure(registrations)
    groups = []
    course_attempts = defaultdict(list)

    for registration in ordered_registrations:
        year, semester = extract_registration_year_semester(registration)
        registration_course_codes = _registration_course_codes(registration)
        group = groups[-1] if groups and _should_merge_with_group(groups[-1], year, semester, registration_course_codes) else None
        if group is None:
            group = {
                "key": f"slot-{len(groups) + 1}",
                "year": year,
                "semester": semester,
                "raw_year": year,
                "raw_semester": semester,
                "year_label": format_year_label(year),
                "semester_label": format_semester_label(semester),
                "academic_level_label": format_academic_level_label(year, semester),
                "period_names": [],
                "registrations": [],
                "results": [],
                "course_codes": set(),
                "latest_registration": registration,
                "sort_key": (
                    year,
                    semester,
                    getattr(getattr(registration, "period", None), "external_id", 0) or 0,
                    registration.id or 0,
                ),
            }
            groups.append(group)

        group["registrations"].append(registration)
        group["course_codes"].update(registration_course_codes)
        period_name = str(getattr(getattr(registration, "period", None), "name", "") or "").strip()
        if period_name and period_name not in group["period_names"]:
            group["period_names"].append(period_name)
        if (
            getattr(getattr(registration, "period", None), "external_id", 0) or 0,
            registration.id or 0,
        ) >= (
            getattr(getattr(group["latest_registration"], "period", None), "external_id", 0) or 0,
            group["latest_registration"].id or 0,
        ):
            group["latest_registration"] = registration
            group["sort_key"] = (
                year,
                semester,
                getattr(getattr(registration, "period", None), "external_id", 0) or 0,
                registration.id or 0,
            )

        registration_results = sorted(
            _registration_results(registration),
            key=lambda result: (
                getattr(getattr(result, "course", None), "code", "") or "",
                getattr(getattr(result, "course", None), "name", "") or "",
                result.id or 0,
            ),
        )
        for result in registration_results:
            course = getattr(result, "course", None)
            course_code = str(getattr(course, "code", "") or "").strip() or f"COURSE-{result.id}"
            previous_attempts = course_attempts[course_code]
            attempt_number = len(previous_attempts) + 1
            mark_value = round(float(result.mark)) if result.mark is not None else None
            is_pass = mark_value is not None and mark_value >= PASS_MARK
            prior_failures = [attempt for attempt in previous_attempts if attempt["mark_value"] is not None and not attempt["is_pass"]]
            original_attempt = previous_attempts[0] if previous_attempts else None

            is_repeat_attempt = attempt_number > 1
            is_carried_attempt = bool(prior_failures) and bool(original_attempt) and (
                original_attempt["year"] != year or original_attempt["semester"] != semester
            )
            is_supplementary_attempt = "supp" in str(result.attendance_type or "").lower()

            attempt_tags = []
            if attempt_number > 1:
                attempt_tags.append(f"Attempt {attempt_number}")
            if is_carried_attempt:
                attempt_tags.append("Carried")
            elif is_repeat_attempt:
                attempt_tags.append("Repeated")
            if is_supplementary_attempt:
                attempt_tags.append("Supplementary")

            suffix = f" ({', '.join(attempt_tags)})" if attempt_tags else ""
            attempt_row = {
                "group_key": group["key"],
                "year": year,
                "semester": semester,
                "academic_year": format_year_label(year),
                "period": format_semester_label(semester),
                "semester_label": format_semester_label(semester),
                "academic_level_label": format_academic_level_label(year, semester),
                "period_name": period_name or format_semester_label(semester),
                "course_code": course_code,
                "course_name": str(getattr(course, "name", "") or "Unknown"),
                "course_display_name": f"{str(getattr(course, 'name', '') or 'Unknown')}{suffix}",
                "mark_value": mark_value,
                "mark": f"{mark_value}%" if mark_value is not None else "--",
                "is_pass": is_pass,
                "is_failing": mark_value is not None and mark_value < PASS_MARK,
                "attempt_number": attempt_number,
                "is_repeat_attempt": is_repeat_attempt,
                "is_carried_attempt": is_carried_attempt,
                "is_supplementary_attempt": is_supplementary_attempt,
                "attempt_tags": attempt_tags,
                "original_year": original_attempt["year"] if original_attempt else year,
                "original_semester": original_attempt["semester"] if original_attempt else semester,
                "registration": registration,
                "result": result,
            }
            group["results"].append(attempt_row)
            previous_attempts.append(attempt_row)

    groups.sort(key=lambda group: group["sort_key"])

    # Imported stage labels can be offset or skip semesters entirely.
    # Rebase the student-facing timeline to contiguous progression slots.
    for index, group in enumerate(groups):
        raw_year = group["raw_year"]
        raw_semester = group["raw_semester"]
        display_year = (index // 2) + 1
        display_semester = 1 if index % 2 == 0 else 2

        group["key"] = f"{display_year}:{display_semester}"
        group["year"] = display_year
        group["semester"] = display_semester
        group["year_label"] = format_year_label(display_year)
        group["semester_label"] = format_semester_label(display_semester)
        group["academic_level_label"] = format_academic_level_label(display_year, display_semester)

        group["results"].sort(
            key=lambda row: (
                row["course_code"],
                -row["attempt_number"],
                row["course_name"],
            )
        )

        for row in group["results"]:
            row["raw_year"] = row["year"]
            row["raw_semester"] = row["semester"]
            row["group_key"] = group["key"]
            row["year"] = display_year
            row["semester"] = display_semester
            row["academic_year"] = format_year_label(display_year)
            row["period"] = format_semester_label(display_semester)
            row["semester_label"] = format_semester_label(display_semester)
            row["academic_level_label"] = format_academic_level_label(display_year, display_semester)

        has_repeat_history = any(row["is_repeat_attempt"] for row in group["results"])
        latest_period_name = str(
            getattr(getattr(group["latest_registration"], "period", None), "name", "") or ""
        ).strip()
        if has_repeat_history and group["period_names"]:
            group["period_display"] = " / ".join(group["period_names"])
        else:
            group["period_display"] = latest_period_name or (group["period_names"][-1] if group["period_names"] else group["semester_label"])
        group.pop("course_codes", None)

    for attempts in course_attempts.values():
        if len(attempts) > 1:
            first_attempt = attempts[0]
            if "First Attempt" not in first_attempt["attempt_tags"]:
                first_attempt["attempt_tags"] = ["First Attempt", *first_attempt["attempt_tags"]]
                first_attempt["course_display_name"] = (
                    f"{first_attempt['course_name']} ({', '.join(first_attempt['attempt_tags'])})"
                )
        for attempt in attempts:
            if attempt["mark_value"] is None:
                attempt["status_label"] = "Awaiting"
            else:
                attempt["status_label"] = "Passed" if attempt["is_pass"] else "Failed"

    return {
        "groups": groups,
        "groups_by_key": {group["key"]: group for group in groups},
    }


def calculate_cumulative_average(groups, selected_group_key=None):
    """Return a non-duplicated cumulative average using each course's latest attempt."""

    if not groups:
        return 0

    latest_results_by_course = {}
    for group in groups:
        for row in group["results"]:
            latest_results_by_course[row["course_code"]] = row
        if selected_group_key and group["key"] == selected_group_key:
            break

    marks = [row["mark_value"] for row in latest_results_by_course.values() if row["mark_value"] is not None]
    if not marks:
        return 0
    return round(sum(marks) / len(marks), 1)


def build_transcript_summary(groups):
    """Build summary totals from the latest attempt per course."""

    latest_results_by_course = {}
    for group in groups:
        for row in group["results"]:
            latest_results_by_course[row["course_code"]] = row

    latest_rows = list(latest_results_by_course.values())
    marks = [row["mark_value"] for row in latest_rows if row["mark_value"] is not None]
    total_courses = len(latest_rows)
    total_passed = sum(1 for row in latest_rows if row["is_pass"])
    total_failed = sum(1 for row in latest_rows if row["mark_value"] is not None and not row["is_pass"])
    average_mark = round(sum(marks) / len(marks), 1) if marks else 0

    return {
        "total_courses": total_courses,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "average_mark": f"{average_mark}%",
        "pass_rate": f"{round((total_passed / total_courses) * 100, 1) if total_courses else 0}%",
        "completion_rate": f"{round((len(marks) / total_courses) * 100, 1) if total_courses else 0}%",
    }

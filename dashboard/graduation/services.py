"""Drilldown services for graduation analysis."""

import logging
from typing import Any, Dict, List

from services.graduation_services import (
    _build_student_histories,
    _graduation_period_label,
    _is_graduated_record,
    _registration_matches_filters,
    _steps_remaining,
    _student_name_sort_key,
    _target_period_from_programme,
)

logger = logging.getLogger(__name__)


def _build_visible_profiles(request) -> List[Dict[str, Any]]:
    """Rebuild the filtered latest-visible student profiles used by graduation charts."""

    year = request.GET.get("year")
    period = request.GET.get("period")
    faculty = request.GET.get("faculty")

    student_histories = _build_student_histories(faculty=faculty)
    profiles: List[Dict[str, Any]] = []
    for history in student_histories:
        visible_records = [
            record
            for record, registration in zip(history["records"], history["registrations"])
            if _registration_matches_filters(registration, year=year, period=period)
        ]
        if not visible_records:
            continue

        latest_visible = max(
            visible_records,
            key=lambda record: (record["period_external_id"], record["registration_id"]),
        )
        target_period = _target_period_from_programme(
            latest_visible["programme_name"],
            latest_visible["regnum"],
        )
        steps_remaining = _steps_remaining(latest_visible, target_period)
        is_graduated = _is_graduated_record(
            latest_visible,
            target_period,
            history.get("start_progression_period"),
        )
        profiles.append(
            {
                "history": history,
                "record": latest_visible,
                "target_period": target_period,
                "steps_remaining": steps_remaining,
                "is_graduated": is_graduated,
            }
        )

    return profiles


def _build_graduated_students(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for profile in profiles:
        if not profile["is_graduated"]:
            continue
        record = profile["record"]
        rows.append(
            {
                "name": record["student_name"],
                "programme": record["programme_name"],
                "department": record.get("department_name", "Unknown"),
                "faculty": record["faculty_name"],
                "graduation_stage": _graduation_period_label(
                    record["programme_name"],
                    record["regnum"],
                ),
                "cohort": record["original_cohort_label"],
                "status": "On time" if record["effective_cohort_label"] == record["original_cohort_label"] else "Delayed",
                "detail_url": f"/students/{str(record['regnum']).lower()}/",
                "regnum": record["regnum"],
                "programme_name": record["programme_name"],
                "department_name": record.get("department_name", "Unknown"),
                "faculty_name": record["faculty_name"],
                "original_cohort": record["original_cohort_label"],
                "effective_cohort": record["effective_cohort_label"],
                "on_time": record["effective_cohort_label"] == record["original_cohort_label"],
            }
        )
    rows.sort(key=lambda row: _student_name_sort_key(row["name"], row["regnum"]))
    return rows


def _build_one_step_students(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for profile in profiles:
        if profile["is_graduated"]:
            continue
        steps_remaining = profile["steps_remaining"]
        if steps_remaining is None or steps_remaining > 1 or steps_remaining < 0:
            continue
        record = profile["record"]
        rows.append(
            {
                "name": record["student_name"],
                "programme": record["programme_name"],
                "department": record.get("department_name", "Unknown"),
                "faculty": record["faculty_name"],
                "graduation_stage": record.get("academic_level_label")
                    or f"Year {record.get('period_year', '')}, Semester {record.get('period_semester', '')}".strip(", "),
                "cohort": record["effective_cohort_label"],
                "status": "One step away" if steps_remaining == 1 else "At target stage",
                "detail_url": f"/students/{str(record['regnum']).lower()}/",
                "regnum": record["regnum"],
                "programme_name": record["programme_name"],
                "department_name": record.get("department_name", "Unknown"),
                "faculty_name": record["faculty_name"],
                "original_cohort": record["original_cohort_label"],
                "effective_cohort": record["effective_cohort_label"],
                "steps_remaining": steps_remaining,
            }
        )
    rows.sort(key=lambda row: _student_name_sort_key(row["name"], row["regnum"]))
    return rows


def _paginate_rows(rows: List[Dict[str, Any]], page: int, page_size: int) -> Dict[str, Any]:
    total_count = len(rows)
    total_pages = max(1, (total_count + page_size - 1) // page_size) if page_size else 1
    safe_page = max(1, min(int(page or 1), total_pages))
    start = (safe_page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]
    return {
        "rows": page_rows,
        "pagination": {
            "current_page": safe_page,
            "page_size": page_size,
            "total_items": total_count,
            "total_pages": total_pages,
            "has_next": safe_page < total_pages,
            "has_previous": safe_page > 1,
        },
        "current_page": safe_page,
        "page_size": page_size,
        "total_items": total_count,
        "total_pages": total_pages,
    }


def build_graduation_drilldown_data(request, chart_key, bucket_key, page=1, page_size=10):
    """Return student rows for graduation analysis chart drill-downs."""

    logger.info(
        "Graduation drilldown called: chart_key=%s bucket_key=%s page=%s",
        chart_key,
        bucket_key,
        page,
    )

    profiles = _build_visible_profiles(request)
    graduated_students = _build_graduated_students(profiles)
    one_step_students = _build_one_step_students(profiles)

    normalized_chart = str(chart_key or "").strip().lower()
    normalized_bucket = str(bucket_key or "").strip()
    filtered_students: List[Dict[str, Any]] = []
    title = f"Students - {bucket_key}"
    subtitle = f"Students for {chart_key}: {bucket_key}"

    if normalized_chart == "faculties":
        filtered_students = [
            student for student in graduated_students
            if student["faculty_name"] == normalized_bucket
        ]
    elif normalized_chart == "departments":
        filtered_students = [
            student for student in graduated_students
            if student["department_name"] == normalized_bucket
        ]
    elif normalized_chart in {"programmes", "programme_load", "graduation_programmes"}:
        filtered_students = [
            student for student in graduated_students
            if student["programme_name"] == normalized_bucket
        ]
    elif normalized_chart == "graduation_cohorts":
        filtered_students = [
            student for student in graduated_students
            if student["original_cohort"] == normalized_bucket
        ]
    elif normalized_chart == "readiness_programmes":
        filtered_students = [
            student for student in one_step_students
            if student["programme_name"] == normalized_bucket
        ]
        title = f"Near-Graduation Students - {bucket_key}"
        subtitle = f"Students one step from graduation in {bucket_key}."
    elif normalized_chart == "readiness_cohorts":
        filtered_students = [
            student for student in one_step_students
            if student["effective_cohort"] == normalized_bucket
        ]
        title = f"Near-Graduation Students - {bucket_key}"
        subtitle = f"Students one step from graduation in effective cohort {bucket_key}."
    elif normalized_chart == "timing":
        filtered_students = [
            student for student in graduated_students
            if (normalized_bucket == "On-time" and student.get("on_time", False))
            or (normalized_bucket == "Delayed" and not student.get("on_time", False))
        ]
    elif normalized_chart == "cohorts":
        filtered_students = [
            student for student in graduated_students
            if student["original_cohort"] == normalized_bucket
        ]
    else:
        filtered_students = graduated_students

    paginated = _paginate_rows(filtered_students, page, page_size)
    return {
        "title": title,
        "subtitle": subtitle,
        "columns": [
            {"key": "name", "label": "Student Name"},
            {"key": "programme", "label": "Programme"},
            {"key": "department", "label": "Department"},
            {"key": "faculty", "label": "Faculty"},
            {"key": "graduation_stage", "label": "Stage"},
            {"key": "cohort", "label": "Cohort"},
            {"key": "status", "label": "Status"},
        ],
        **paginated,
    }

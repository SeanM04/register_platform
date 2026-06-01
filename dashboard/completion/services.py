"""Drilldown services for completion analysis."""

import logging
from urllib.parse import unquote_plus

from services.completion_service import get_cached_completion_page_data

logger = logging.getLogger(__name__)


def build_completion_drilldown_data(request, chart_key, bucket_key, page=1, page_size=10):
    """Return student rows for completion analysis chart drill-downs."""

    bucket_key = unquote_plus(bucket_key)
    year = request.GET.get("year")
    period = request.GET.get("period")
    faculty = request.GET.get("faculty")

    logger.info(
        "Completion drilldown called: chart_key=%s bucket_key=%s page=%s",
        chart_key,
        bucket_key,
        page,
    )

    completion_data = get_cached_completion_page_data(
        year=year,
        period=period,
        faculty=faculty,
    )
    visible_students = list(completion_data.get("students") or [])

    normalized_chart = str(chart_key or "").strip().lower()
    normalized_bucket = str(bucket_key or "").strip().lower()

    if normalized_chart == "drivers":
        filtered_students = [
            student for student in visible_students
            if str(student.get("zero_completion_reason") or "").strip().lower() == normalized_bucket
        ]
        title = f"Students - {bucket_key}"
        subtitle = f"Students currently linked to {bucket_key}."
    elif normalized_chart == "programme_load":
        filtered_students = [
            student for student in visible_students
            if str(student.get("programme_name") or "").strip().lower() == normalized_bucket
            or str(student.get("programme_normalized_name") or "").strip().lower() == normalized_bucket
        ]
        title = f"Students - {bucket_key}"
        subtitle = f"Students currently visible in {bucket_key}."
    elif normalized_chart == "cohorts":
        filtered_students = [
            student for student in visible_students
            if str(student.get("original_cohort") or "").strip().lower() == normalized_bucket
            or str(student.get("effective_cohort") or "").strip().lower() == normalized_bucket
        ]
        title = f"Students - {bucket_key}"
        subtitle = f"Students currently attached to cohort {bucket_key}."
    else:
        filtered_students = visible_students
        title = f"Students - {bucket_key}"
        subtitle = f"Students for {chart_key}: {bucket_key}"

    filtered_students.sort(
        key=lambda student: (
            str(student.get("student_name") or "").split()[-1].lower(),
            " ".join(str(student.get("student_name") or "").split()[:-1]).lower(),
            str(student.get("regnum") or "").lower(),
        )
    )

    total_count = len(filtered_students)
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count else 1
    safe_page = max(1, min(int(page or 1), total_pages))
    offset = (safe_page - 1) * page_size
    paginated_students = filtered_students[offset:offset + page_size]

    student_rows = [
        {
            "name": student.get("student_name", ""),
            "programme": student.get("programme_name", "Unassigned"),
            "academic_stage": str(student.get("academic_stage") or "").replace(", ", " "),
            "decision": student.get("decision", "Unknown"),
            "effective_cohort": student.get("effective_cohort", ""),
            "completion_rate": f"{round(float(student.get('completion_rate') or 0))}%",
            "detail_url": f"/students/{student.get('detail_slug') or str(student.get('regnum') or '').lower()}/",
        }
        for student in paginated_students
    ]

    return {
        "title": title,
        "subtitle": subtitle,
        "columns": [
            {"key": "name", "label": "Student Name"},
            {"key": "programme", "label": "Programme"},
            {"key": "academic_stage", "label": "Academic Stage"},
            {"key": "decision", "label": "Decision"},
            {"key": "effective_cohort", "label": "Effective Cohort"},
            {"key": "completion_rate", "label": "Completion Rate"},
        ],
        "rows": student_rows,
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

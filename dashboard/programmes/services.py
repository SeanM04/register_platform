"""Service-layer data shaping for the story-first programmes dashboard."""

from collections import defaultdict

from django.db.models import Avg, Count, Q

from ..models import Programme
from ..views import build_registration_filter_q
from .constants import PROGRAMME_SUMMARY_CARD_SPECS


def _pct(count, total):
    """Return a rounded percentage while safely handling empty totals."""

    return round((count / total) * 100) if total else 0


def _format_count(value):
    """Format integers with grouping for short note copy."""

    return f"{int(value or 0):,}"


def _truncate_text(value, max_length=34):
    """Clamp long labels so note and banner copy stay readable."""

    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - 3].rstrip()}..."


def get_programmes_queryset(request, search_query=""):
    """Return annotated programmes for the current dashboard filter scope."""

    programme_filter = build_registration_filter_q(request, prefix="registrations__")
    programmes = (
        Programme.objects.select_related("department__faculty")
        .annotate(
            registration_count=Count("registrations", filter=programme_filter, distinct=True),
            student_count=Count("registrations__student", filter=programme_filter, distinct=True),
            average_mark=Avg(
                "registrations__course_results__mark",
                filter=programme_filter & Q(registrations__course_results__mark__isnull=False),
            ),
            pass_count=Count(
                "registrations__course_results",
                filter=programme_filter & Q(registrations__course_results__mark__gte=50),
                distinct=True,
            ),
            fail_count=Count(
                "registrations__course_results",
                filter=programme_filter & Q(registrations__course_results__mark__lt=50),
                distinct=True,
            ),
            mark_count=Count(
                "registrations__course_results",
                filter=programme_filter & Q(registrations__course_results__mark__isnull=False),
                distinct=True,
            ),
        )
        .filter(registration_count__gt=0)
        .order_by("name")
    )

    if search_query:
        programmes = programmes.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(department__name__icontains=search_query)
            | Q(department__faculty__name__icontains=search_query)
        )

    return programmes


def build_programme_rows(programmes):
    """Transform annotated programme queryset rows for template and chart rendering."""

    programme_rows = []
    for programme in programmes:
        marked_results = int(programme.mark_count or 0)
        pass_count = int(programme.pass_count or 0)
        fail_count = int(programme.fail_count or 0)
        pass_rate_value = round((pass_count / marked_results) * 100) if marked_results else 0
        average_mark_value = round(float(programme.average_mark or 0), 1)

        department = programme.department.name if programme.department else "Unassigned"
        faculty = programme.department.faculty.name if programme.department and programme.department.faculty else "Unassigned"

        programme_rows.append(
            {
                "code": programme.code,
                "name": programme.name,
                "faculty": faculty,
                "department": department,
                "students": int(programme.student_count or 0),
                "registrations": int(programme.registration_count or 0),
                "marked_results": marked_results,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "average_mark": round(average_mark_value),
                "average_mark_value": average_mark_value,
                "pass_rate": f"{pass_rate_value}%",
                "pass_rate_value": pass_rate_value,
            }
        )

    return programme_rows


def _build_summary_values_from_rows(programme_rows):
    """Calculate summary metrics from already-shaped programme rows."""

    total_registrations = sum(row["registrations"] for row in programme_rows)
    total_students = sum(row["students"] for row in programme_rows)
    total_marked_results = sum(row["marked_results"] for row in programme_rows)
    total_passes = sum(row["pass_count"] for row in programme_rows)
    weighted_pass_rate = round((total_passes / total_marked_results) * 100) if total_marked_results else 0

    return {
        "programmes": len(programme_rows),
        "registrations": total_registrations,
        "students": total_students,
        "average_pass_rate": f"{weighted_pass_rate}%",
        "average_pass_rate_value": weighted_pass_rate,
        "pass_count": total_passes,
        "marked_results": total_marked_results,
    }


def get_programme_summary_values(request, search_query=""):
    """Calculate programme summary metrics for asynchronous loading."""

    programme_rows = build_programme_rows(get_programmes_queryset(request, search_query))
    return _build_summary_values_from_rows(programme_rows)


def build_programme_scope_pills(request, search_query=""):
    """Build compact scope pills describing the active programme filter context."""

    selected_faculty = request.GET.get("faculty", "").strip()
    selected_period = request.GET.get("period", "").strip()
    selected_year = request.GET.get("year", "").strip()

    pills = [
        {
            "label": "Filtered programmes" if any([selected_faculty, selected_period, selected_year, search_query]) else "Live programmes",
            "variant": "live",
        }
    ]

    if selected_faculty:
        pills.append({"label": f"Faculty: {selected_faculty}", "variant": "scope"})
    if selected_period:
        pills.append({"label": f"Period: {selected_period}", "variant": "scope"})
    if selected_year:
        pills.append({"label": f"Year: {selected_year}", "variant": "scope"})
    if search_query:
        pills.append({"label": f"Search: {search_query}", "variant": "scope"})

    if len(pills) == 1:
        pills.append({"label": "All faculties", "variant": "scope"})
        pills.append({"label": "All periods", "variant": "scope"})
        pills.append({"label": "All years", "variant": "scope"})

    return pills


def _build_summary_cards(summary_values, programme_rows):
    """Build the four programme summary cards shown above the story banner."""

    lead_programme = (
        sorted(programme_rows, key=lambda row: (-row["registrations"], row["name"]))[0]
        if programme_rows
        else None
    )

    notes = {
        "programmes": f"{_format_count(summary_values['programmes'])} active programme portfolios are visible in scope.",
        "registrations": (
            f"{_truncate_text(lead_programme['name'])} carries {round((lead_programme['registrations'] / summary_values['registrations']) * 100)}% of visible load."
            if lead_programme and summary_values["registrations"]
            else "Registration concentration will appear once records are available."
        ),
        "students": f"Across {_format_count(summary_values['students'])} unique student appearances in the visible programme mix.",
        "average_pass_rate": (
            f"{_format_count(summary_values['pass_count'])} of {_format_count(summary_values['marked_results'])} marked module results are currently passing."
            if summary_values["marked_results"]
            else "Marked assessment results are not available for the active scope."
        ),
    }

    cards = []
    for spec in PROGRAMME_SUMMARY_CARD_SPECS:
        tone = spec["tone"]
        if spec["key"] == "average_pass_rate":
            if summary_values["average_pass_rate_value"] < 60:
                tone = "danger"
            elif summary_values["average_pass_rate_value"] >= 80:
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


def _build_top_load_rows(programme_rows):
    """Build the ranked load chart rows for the hero programme chart."""

    total_registrations = sum(row["registrations"] for row in programme_rows)
    rows = [
        {
            **row,
            "share_pct": _pct(row["registrations"], total_registrations),
        }
        for row in sorted(
            programme_rows,
            key=lambda row: (-row["registrations"], -row["students"], row["name"]),
        )[:8]
    ]
    return rows


def _build_department_rows(programme_rows):
    """Aggregate visible programme load into department-level portfolio rows."""

    grouped_rows = defaultdict(
        lambda: {
            "faculty": "",
            "department": "",
            "registrations": 0,
            "students": 0,
            "marked_results": 0,
            "pass_count": 0,
            "programme_count": 0,
            "average_mark_total": 0.0,
            "average_mark_weight": 0,
        }
    )

    for row in programme_rows:
        key = (row["faculty"], row["department"])
        bucket = grouped_rows[key]
        bucket["faculty"] = row["faculty"]
        bucket["department"] = row["department"]
        bucket["registrations"] += row["registrations"]
        bucket["students"] += row["students"]
        bucket["marked_results"] += row["marked_results"]
        bucket["pass_count"] += row["pass_count"]
        bucket["programme_count"] += 1
        if row["marked_results"]:
            bucket["average_mark_total"] += row["average_mark_value"] * row["marked_results"]
            bucket["average_mark_weight"] += row["marked_results"]

    total_registrations = sum(row["registrations"] for row in programme_rows)
    rows = []
    for bucket in grouped_rows.values():
        average_mark_value = (
            round(bucket["average_mark_total"] / bucket["average_mark_weight"], 1)
            if bucket["average_mark_weight"]
            else 0
        )
        pass_rate_value = (
            round((bucket["pass_count"] / bucket["marked_results"]) * 100)
            if bucket["marked_results"]
            else 0
        )
        rows.append(
            {
                "faculty": bucket["faculty"],
                "department": bucket["department"],
                "registrations": bucket["registrations"],
                "students": bucket["students"],
                "programme_count": bucket["programme_count"],
                "share_pct": _pct(bucket["registrations"], total_registrations),
                "average_mark_value": average_mark_value,
                "average_mark": round(average_mark_value),
                "pass_rate_value": pass_rate_value,
                "pass_rate": f"{pass_rate_value}%",
            }
        )

    rows.sort(key=lambda row: (-row["registrations"], -row["programme_count"], row["department"]))
    return rows[:8]


def _build_low_pass_rows(programme_rows):
    """Build the weakest-pass-rate programme rows for the quality chapter."""

    rows = [
        row
        for row in programme_rows
        if row["marked_results"] > 0
    ]
    rows.sort(key=lambda row: (row["pass_rate_value"], row["average_mark_value"], -row["registrations"], row["name"]))
    return rows[:8]


def _build_performance_rows(programme_rows):
    """Build the registrations-versus-pass-rate performance map rows."""

    rows = [
        row
        for row in programme_rows
        if row["registrations"] > 0 and row["marked_results"] > 0
    ]
    rows.sort(key=lambda row: (-row["registrations"], row["pass_rate_value"], row["name"]))
    return rows[:14]


def build_programme_dashboard_data(request, search_query=""):
    """Assemble the story-first programme dashboard payload."""

    programme_rows = build_programme_rows(get_programmes_queryset(request, search_query))
    summary_values = _build_summary_values_from_rows(programme_rows)

    return {
        "summary_cards": _build_summary_cards(summary_values, programme_rows),
        "scope_pills": build_programme_scope_pills(request, search_query),
        "programme_rows": programme_rows,
        "top_load_rows": _build_top_load_rows(programme_rows),
        "department_rows": _build_department_rows(programme_rows),
        "low_pass_rows": _build_low_pass_rows(programme_rows),
        "performance_rows": _build_performance_rows(programme_rows),
    }

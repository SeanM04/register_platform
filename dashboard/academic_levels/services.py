"""Service-layer logic for academic-level analytics."""

from django.db.models import Q

from ..views import (
    GENDER_BUCKETS,
    format_academic_level_label,
    get_filtered_registrations,
    normalize_gender_key,
)

from .constants import ACADEMIC_LEVEL_PASS_TARGET


def get_academic_level_registrations(request, search_query=""):
    """Return academic-level registrations shaped by the page filters and search."""

    registrations = get_filtered_registrations(request)
    if search_query:
        registrations = registrations.filter(
            Q(period__academic_year__icontains=search_query)
            | Q(period__semester__icontains=search_query)
            | Q(programme__name__icontains=search_query)
            | Q(programme__department__name__icontains=search_query)
        )

    return registrations


def build_academic_level_data(request, search_query=""):
    """Build table rows plus graph-ready academic-level breakdowns."""

    registrations = get_academic_level_registrations(request, search_query)
    level_map = {}
    programme_map = {}
    gender_map = {
        key: {
            "label": label,
            "students": set(),
            "marks_total": 0,
            "mark_count": 0,
            "pass_count": 0,
        }
        for key, label in GENDER_BUCKETS
    }

    for registration in registrations:
        year = registration.period.academic_year or "?"
        semester = registration.period.semester or "?"
        level_key = f"{year}.{semester}"
        level_label = format_academic_level_label(year, semester)
        gender_key = normalize_gender_key(registration.student.gender)
        programme_name = registration.programme.normalized_name

        if level_key not in level_map:
            level_map[level_key] = {
                "level": level_label,
                "sort_year": int(year) if str(year).isdigit() else 0,
                "sort_semester": int(semester) if str(semester).isdigit() else 0,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
                "programme_counts": {},
                "programme_breakdown": {},
                "gender_students": {key: set() for key, _ in GENDER_BUCKETS},
            }

        if programme_name not in programme_map:
            programme_map[programme_name] = {
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
                "level_counts": {},
                "level_breakdown": {},
            }

        level_map[level_key]["registrations"] += 1
        level_map[level_key]["students"].add(registration.student_id)
        level_map[level_key]["programme_counts"][programme_name] = (
            level_map[level_key]["programme_counts"].get(programme_name, 0) + 1
        )
        level_map[level_key]["gender_students"][gender_key].add(registration.student_id)

        if programme_name not in level_map[level_key]["programme_breakdown"]:
            level_map[level_key]["programme_breakdown"][programme_name] = {
                "programme": programme_name,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
            }

        level_map[level_key]["programme_breakdown"][programme_name]["registrations"] += 1
        level_map[level_key]["programme_breakdown"][programme_name]["students"].add(registration.student_id)

        gender_map[gender_key]["students"].add(registration.student_id)

        programme_map[programme_name]["registrations"] += 1
        programme_map[programme_name]["students"].add(registration.student_id)
        programme_map[programme_name]["level_counts"][level_label] = (
            programme_map[programme_name]["level_counts"].get(level_label, 0) + 1
        )

        if level_label not in programme_map[programme_name]["level_breakdown"]:
            programme_map[programme_name]["level_breakdown"][level_label] = {
                "level": level_label,
                "sort_year": int(year) if str(year).isdigit() else 0,
                "sort_semester": int(semester) if str(semester).isdigit() else 0,
                "registrations": 0,
                "students": set(),
                "marks_total": 0,
                "mark_count": 0,
                "pass_count": 0,
            }

        programme_map[programme_name]["level_breakdown"][level_label]["registrations"] += 1
        programme_map[programme_name]["level_breakdown"][level_label]["students"].add(registration.student_id)

        for result in registration.course_results.all():
            if result.mark is None:
                continue
            mark_value = float(result.mark)

            level_map[level_key]["marks_total"] += mark_value
            level_map[level_key]["mark_count"] += 1
            level_map[level_key]["programme_breakdown"][programme_name]["marks_total"] += mark_value
            level_map[level_key]["programme_breakdown"][programme_name]["mark_count"] += 1
            gender_map[gender_key]["marks_total"] += mark_value
            gender_map[gender_key]["mark_count"] += 1
            programme_map[programme_name]["marks_total"] += mark_value
            programme_map[programme_name]["mark_count"] += 1
            programme_map[programme_name]["level_breakdown"][level_label]["marks_total"] += mark_value
            programme_map[programme_name]["level_breakdown"][level_label]["mark_count"] += 1

            if mark_value >= 50:
                level_map[level_key]["pass_count"] += 1
                level_map[level_key]["programme_breakdown"][programme_name]["pass_count"] += 1
                gender_map[gender_key]["pass_count"] += 1
                programme_map[programme_name]["pass_count"] += 1
                programme_map[programme_name]["level_breakdown"][level_label]["pass_count"] += 1

    level_rows = []
    level_chart_rows = []
    for item in sorted(level_map.values(), key=lambda row: (row["sort_year"], row["sort_semester"])):
        top_programme = ""
        if item["programme_counts"]:
            top_programme = max(item["programme_counts"].items(), key=lambda entry: entry[1])[0]

        mark_count = item["mark_count"]
        avg_mark = round(item["marks_total"] / mark_count) if mark_count else 0
        pass_rate = round((item["pass_count"] / mark_count) * 100) if mark_count else 0
        student_count = len(item["students"])
        programme_breakdown_rows = []
        for programme_breakdown in item["programme_breakdown"].values():
            breakdown_mark_count = programme_breakdown["mark_count"]
            breakdown_average_mark = (
                round(programme_breakdown["marks_total"] / breakdown_mark_count)
                if breakdown_mark_count
                else 0
            )
            breakdown_pass_rate = (
                round((programme_breakdown["pass_count"] / breakdown_mark_count) * 100)
                if breakdown_mark_count
                else 0
            )
            programme_breakdown_rows.append(
                {
                    "programme": programme_breakdown["programme"],
                    "registrations": programme_breakdown["registrations"],
                    "students": len(programme_breakdown["students"]),
                    "average_mark": breakdown_average_mark,
                    "average_mark_display": breakdown_average_mark if breakdown_mark_count else "--",
                    "pass_rate": f"{breakdown_pass_rate}%",
                    "pass_rate_value": breakdown_pass_rate,
                    "results": breakdown_mark_count,
                }
            )

        programme_breakdown_rows.sort(
            key=lambda row: (-row["registrations"], -row["average_mark"], -row["pass_rate_value"], row["programme"])
        )

        level_rows.append(
            {
                "level": item["level"],
                "students": student_count,
                "registrations": item["registrations"],
                "average_mark": avg_mark,
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
                "below_target": pass_rate < ACADEMIC_LEVEL_PASS_TARGET,
                "top_programme": top_programme,
            }
        )
        level_chart_rows.append(
            {
                "level": item["level"],
                "students": student_count,
                "registrations": item["registrations"],
                "average_mark": avg_mark,
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
                "top_programme": top_programme,
                "male_count": len(item["gender_students"]["male"]),
                "female_count": len(item["gender_students"]["female"]),
                "unspecified_count": len(item["gender_students"]["unspecified"]),
                "programme_breakdown": programme_breakdown_rows,
            }
        )

    total_students = len({student_id for data in gender_map.values() for student_id in data["students"]})
    gender_performance_rows = []
    for key, label in GENDER_BUCKETS:
        item = gender_map[key]
        student_count = len(item["students"])
        mark_count = item["mark_count"]
        avg_mark = round(item["marks_total"] / mark_count) if mark_count else 0
        pass_rate = round((item["pass_count"] / mark_count) * 100) if mark_count else 0
        student_share = round((student_count / total_students) * 100) if total_students else 0

        gender_performance_rows.append(
            {
                "key": key,
                "label": label,
                "students": student_count,
                "student_share": f"{student_share}%",
                "student_share_value": student_share,
                "results": mark_count,
                "average_mark": avg_mark,
                "average_mark_display": avg_mark if mark_count else "--",
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
            }
        )

    programme_performance_rows = []
    for programme_name, item in programme_map.items():
        mark_count = item["mark_count"]
        if not mark_count:
            continue

        avg_mark = round(item["marks_total"] / mark_count)
        pass_rate = round((item["pass_count"] / mark_count) * 100)
        lead_level = (
            max(item["level_counts"].items(), key=lambda entry: (entry[1], entry[0]))[0]
            if item["level_counts"]
            else ""
        )
        level_breakdown_rows = []
        for breakdown in sorted(
            item["level_breakdown"].values(),
            key=lambda row: (row["sort_year"], row["sort_semester"]),
        ):
            breakdown_mark_count = breakdown["mark_count"]
            breakdown_average_mark = (
                round(breakdown["marks_total"] / breakdown_mark_count)
                if breakdown_mark_count
                else 0
            )
            breakdown_pass_rate = (
                round((breakdown["pass_count"] / breakdown_mark_count) * 100)
                if breakdown_mark_count
                else 0
            )
            level_breakdown_rows.append(
                {
                    "level": breakdown["level"],
                    "registrations": breakdown["registrations"],
                    "students": len(breakdown["students"]),
                    "average_mark": breakdown_average_mark,
                    "pass_rate": f"{breakdown_pass_rate}%",
                    "pass_rate_value": breakdown_pass_rate,
                }
            )

        programme_performance_rows.append(
            {
                "programme": programme_name,
                "students": len(item["students"]),
                "registrations": item["registrations"],
                "average_mark": avg_mark,
                "average_mark_display": avg_mark if mark_count else "--",
                "pass_rate": f"{pass_rate}%",
                "pass_rate_value": pass_rate,
                "lead_level": lead_level,
                "level_breakdown": level_breakdown_rows,
            }
        )

    programme_performance_rows.sort(
        key=lambda row: (-row["pass_rate_value"], -row["average_mark"], -row["registrations"], row["programme"])
    )

    return {
        "level_rows": level_rows,
        "level_chart_rows": level_chart_rows,
        "gender_performance_rows": gender_performance_rows,
        "programme_performance_rows": programme_performance_rows,
    }


def get_academic_level_summary_values(request, search_query=""):
    """Calculate academic-level summary metrics for asynchronous loading."""

    level_rows = build_academic_level_data(request, search_query)["level_rows"]
    return {
        "levels": len(level_rows),
        "registrations": sum(row["registrations"] for row in level_rows),
        "students": sum(row["students"] for row in level_rows),
        "average_pass_rate": (
            f"{round(sum(int(row['pass_rate'].replace('%', '')) for row in level_rows) / len(level_rows))}%"
            if level_rows
            else "0%"
        ),
    }

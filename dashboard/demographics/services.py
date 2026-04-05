"""Service-layer logic for demographics analytics."""

from django.db.models import Q

from ..views import get_filtered_registrations, normalize_gender_key
from .constants import BIRTH_LOCATION_MAP_ALIASES, BIRTH_LOCATION_MAP_POINTS


def _format_share(count, total_students):
    """Return a whole-number percentage string for a visible cohort count."""

    return f"{round((count / total_students) * 100) if total_students else 0}%"


def _normalize_location_map_key(place):
    """Normalize a birth-location label before looking up map coordinates."""

    normalized = str(place or "").strip().lower()
    for token in [",", "-", "/", "(", ")", "."]:
        normalized = normalized.replace(token, " ")

    normalized = " ".join(normalized.split())
    return BIRTH_LOCATION_MAP_ALIASES.get(normalized, normalized)


def build_demographic_data(request, search_query=""):
    """Build demographic tables and supporting counts from filtered registrations."""

    registrations = get_filtered_registrations(request)
    if search_query:
        registrations = registrations.filter(
            Q(student__first_names__icontains=search_query)
            | Q(student__surname__icontains=search_query)
            | Q(student__gender__icontains=search_query)
            | Q(student__place_of_birth__icontains=search_query)
            | Q(programme__name__icontains=search_query)
        )

    unique_students = {}
    for registration in registrations:
        unique_students[registration.student.registration_number] = {
            "student": registration.student,
            "programme": registration.programme,
        }

    student_values = list(unique_students.values())
    total_students = len(student_values)
    male_count = sum(1 for item in student_values if normalize_gender_key(item["student"].gender) == "male")
    female_count = sum(1 for item in student_values if normalize_gender_key(item["student"].gender) == "female")
    unspecified_count = total_students - male_count - female_count

    gender_rows = [
        {
            "label": "Male",
            "count": male_count,
            "share": _format_share(male_count, total_students),
        },
        {
            "label": "Female",
            "count": female_count,
            "share": _format_share(female_count, total_students),
        },
        {
            "label": "Unspecified",
            "count": unspecified_count,
            "share": _format_share(unspecified_count, total_students),
        },
    ]

    location_gender_counts = {}
    programme_gender_counts = {}
    for item in student_values:
        place = item["student"].place_of_birth.strip() or "Unspecified"
        if place not in location_gender_counts:
            location_gender_counts[place] = {"male": 0, "female": 0, "unspecified": 0}

        gender_key = normalize_gender_key(item["student"].gender)
        location_gender_counts[place][gender_key] += 1

        programme_name = item["programme"].name
        if programme_name not in programme_gender_counts:
            programme_gender_counts[programme_name] = {"male": 0, "female": 0, "unspecified": 0}

        programme_gender_counts[programme_name][gender_key] += 1

    sorted_location_items = sorted(
        location_gender_counts.items(),
        key=lambda item: (-(item[1]["male"] + item[1]["female"] + item[1]["unspecified"]), item[0]),
    )

    location_rows = [
        {
            "place": place,
            "count": counts["male"] + counts["female"] + counts["unspecified"],
            "share": _format_share(counts["male"] + counts["female"] + counts["unspecified"], total_students),
        }
        for place, counts in sorted_location_items[:10]
    ]

    location_mix_rows = [
        {
            "place": place,
            "male": counts["male"],
            "female": counts["female"],
            "unspecified": counts["unspecified"],
            "total": counts["male"] + counts["female"] + counts["unspecified"],
            "share": _format_share(counts["male"] + counts["female"] + counts["unspecified"], total_students),
        }
        for place, counts in sorted_location_items[:10]
    ]

    location_map_rows = []
    unmapped_places = []
    unmapped_students = 0
    mapped_students = 0
    for place, counts in sorted_location_items:
        total = counts["male"] + counts["female"] + counts["unspecified"]
        map_key = _normalize_location_map_key(place)
        map_point = BIRTH_LOCATION_MAP_POINTS.get(map_key)
        if map_point:
            location_map_rows.append(
                {
                    "place": place,
                    "count": total,
                    "share": _format_share(total, total_students),
                    "male": counts["male"],
                    "female": counts["female"],
                    "unspecified": counts["unspecified"],
                    "lng": map_point["lng"],
                    "lat": map_point["lat"],
                    "province": map_point["province"],
                }
            )
            mapped_students += total
            continue

        if place != "Unspecified" and total:
            unmapped_places.append(place)
            unmapped_students += total

    location_map_meta = {
        "mapped_places": len(location_map_rows),
        "mapped_students": mapped_students,
        "unmapped_places": len(unmapped_places),
        "unmapped_students": unmapped_students,
        "unmapped_labels": unmapped_places[:5],
    }

    programme_rows = [
        {
            "programme": programme_name,
            "male": counts["male"],
            "female": counts["female"],
            "unspecified": counts["unspecified"],
            "total": counts["male"] + counts["female"] + counts["unspecified"],
        }
        for programme_name, counts in sorted(
            programme_gender_counts.items(),
            key=lambda item: (-(item[1]["male"] + item[1]["female"] + item[1]["unspecified"]), item[0]),
        )[:12]
    ]

    return {
        "total_students": total_students,
        "male_count": male_count,
        "female_count": female_count,
        "location_counts": {
            place: counts["male"] + counts["female"] + counts["unspecified"]
            for place, counts in location_gender_counts.items()
        },
        "gender_rows": gender_rows,
        "location_rows": location_rows,
        "location_mix_rows": location_mix_rows,
        "location_map_rows": location_map_rows,
        "location_map_meta": location_map_meta,
        "programme_rows": programme_rows,
    }


def get_demographic_summary_values(request, search_query=""):
    """Calculate demographic summary metrics for asynchronous loading."""

    demographic_data = build_demographic_data(request, search_query)
    return {
        "students": demographic_data["total_students"],
        "male": demographic_data["male_count"],
        "female": demographic_data["female_count"],
        "birth_locations": len(demographic_data["location_counts"]),
    }

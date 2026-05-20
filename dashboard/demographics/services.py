"""Service-layer logic for demographics analytics."""

from collections import defaultdict
from datetime import date

from django.db.models import Q
from django.utils import timezone

from ..models import Registration
from services.completion_service import _build_progression_overrides, _cohort_period_map
from ..student_history import extract_registration_year_semester
from ..views import build_registration_filter_q, normalize_gender_key
from .constants import BIRTH_LOCATION_MAP_ALIASES, BIRTH_LOCATION_MAP_POINTS

DEMOGRAPHIC_LOCATION_LIMIT = 10
DEMOGRAPHIC_PROGRAMME_LIMIT = 20
DEMOGRAPHIC_ITERATOR_CHUNK_SIZE = 2000
# Academic levels shown on year distribution (cohort progression within programme)
ACADEMIC_YEAR_LEVEL_KEYS = ("1", "2", "3", "4", "5")
AGE_GROUP_SPECS = (
    ("Under 20", 0, 19),
    ("20-24", 20, 24),
    ("25-29", 25, 29),
    ("30-34", 30, 34),
    ("35+", 35, None),
)


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


def _empty_gender_counts():
    """Return a fresh gender-count container for grouped aggregations."""

    return {"male": 0, "female": 0, "unspecified": 0}


def _calculate_age_from_dob(date_of_birth):
    """Calculate age from date of birth."""
    if not date_of_birth:
        return None
    
    today = timezone.localdate()
    years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


def build_registration_pk_to_progression_year_map(student_ids):
    """
    Map each registration PK to the cohort-timeline progression year used by completion heatmaps.
    """
    if not student_ids:
        return {}
    rows = list(
        Registration.objects.filter(student_id__in=student_ids)
        .select_related("period")
        .order_by("student_id", "period__external_id", "id")
    )
    period_index_map, _, _ = _cohort_period_map()
    registrations_by_student = defaultdict(list)
    for registration in rows:
        registrations_by_student[registration.student_id].append(registration)

    progression_year_map = {}
    for student_registrations in registrations_by_student.values():
        progression_overrides = _build_progression_overrides(student_registrations, period_index_map)
        for registration in student_registrations:
            override = progression_overrides.get(registration.id, {})
            progression_index = override.get("progression_period_index")
            if progression_index is not None:
                progression_year_map[registration.id] = ((int(progression_index) - 1) // 2) + 1
                continue
            progression_year_map[registration.id] = extract_registration_year_semester(registration)[0]

    return progression_year_map


def _age_group_for_years(age):
    """Return the configured display bucket for an age value."""

    if age is None:
        return None

    for label, minimum, maximum in AGE_GROUP_SPECS:
        if age < minimum:
            continue
        if maximum is None or age <= maximum:
            return label
    return None


def _get_demographic_registration_rows(request, search_query=""):
    """Yield the latest filtered registration row for each visible student."""

    registrations = Registration.objects.filter(build_registration_filter_q(request))
    if search_query:
        registrations = registrations.filter(
            Q(student__first_names__icontains=search_query)
            | Q(student__surname__icontains=search_query)
            | Q(student__gender__icontains=search_query)
            | Q(student__place_of_birth__icontains=search_query)
            | Q(programme__name__icontains=search_query)
        )

    latest_first_rows = (
        registrations.order_by("student__registration_number", "-period__external_id", "-id").values(
            "id",
            "student_id",
            "student__registration_number",
            "student__gender",
            "student__date_of_birth",
            "student__place_of_birth",
            "programme__name",
            "programme__code",
            "period__external_id",
        )
    )

    seen_students = set()
    for row in latest_first_rows.iterator(chunk_size=DEMOGRAPHIC_ITERATOR_CHUNK_SIZE):
        registration_number = row["student__registration_number"]
        if registration_number in seen_students:
            continue
        seen_students.add(registration_number)
        yield row


def build_demographic_data(request, search_query=""):
    """Build demographic tables and supporting counts from filtered registrations."""

    total_students = 0
    male_count = 0
    female_count = 0
    location_gender_counts = defaultdict(_empty_gender_counts)
    programme_gender_counts = defaultdict(_empty_gender_counts)
    age_gender_counts = {label: _empty_gender_counts() for label, _, _ in AGE_GROUP_SPECS}
    programme_code_map = {}
    year_gender_counts = defaultdict(_empty_gender_counts)

    registration_rows = list(_get_demographic_registration_rows(request, search_query))
    student_ids = {row["student_id"] for row in registration_rows if row.get("student_id")}
    reg_to_progression_year = build_registration_pk_to_progression_year_map(student_ids)

    for row in registration_rows:
        total_students += 1
        gender_key = normalize_gender_key(row["student__gender"])
        if gender_key == "male":
            male_count += 1
        elif gender_key == "female":
            female_count += 1

        place = str(row["student__place_of_birth"] or "").strip() or "Unspecified"
        location_gender_counts[place][gender_key] += 1

        # Calculate age from date of birth
        date_of_birth = row.get("student__date_of_birth")
        age = _calculate_age_from_dob(date_of_birth)
        age_group = _age_group_for_years(age)
        if age_group:
            age_gender_counts[age_group][gender_key] += 1

        programme_name = str(row["programme__name"] or "").strip() or "Unspecified programme"
        programme_name = programme_name.replace("Bsc", "BSc").replace("Bcom", "BCom")
        programme_code = str(row["programme__code"] or "").strip() or "N/A"
        programme_gender_counts[programme_name][gender_key] += 1
        programme_code_map[programme_name] = programme_code

        reg_id = row.get("id")
        progression_year = reg_to_progression_year.get(reg_id) if reg_id is not None else None
        if progression_year is not None:
            year_gender_counts[str(progression_year)][gender_key] += 1

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
        for place, counts in sorted_location_items[:DEMOGRAPHIC_LOCATION_LIMIT]
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
        for place, counts in sorted_location_items[:DEMOGRAPHIC_LOCATION_LIMIT]
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
            "programme_code": programme_code_map.get(programme_name, "N/A"),
            "male": counts["male"],
            "female": counts["female"],
            "unspecified": counts["unspecified"],
            "total": counts["male"] + counts["female"] + counts["unspecified"],
        }
        for programme_name, counts in sorted(
            programme_gender_counts.items(),
            key=lambda item: (-(item[1]["male"] + item[1]["female"] + item[1]["unspecified"]), item[0]),
        )[:DEMOGRAPHIC_PROGRAMME_LIMIT]
    ]

    programme_gender_rows = [
        {
            "programme": programme_name,
            "programme_code": programme_code_map.get(programme_name, "N/A"),
            "male": counts["male"],
            "female": counts["female"],
            "male_share": _format_share(counts["male"], counts["male"] + counts["female"] + counts["unspecified"]),
            "female_share": _format_share(counts["female"], counts["male"] + counts["female"] + counts["unspecified"]),
            "total": counts["male"] + counts["female"] + counts["unspecified"],
        }
        for programme_name, counts in sorted(
            programme_gender_counts.items(),
            key=lambda item: (-(item[1]["male"] + item[1]["female"] + item[1]["unspecified"]), item[0]),
        )[:DEMOGRAPHIC_PROGRAMME_LIMIT]
    ]

    year_distribution_rows = []
    for year in ACADEMIC_YEAR_LEVEL_KEYS:
        counts = year_gender_counts.get(year, _empty_gender_counts())
        row_total = counts["male"] + counts["female"] + counts["unspecified"]
        year_distribution_rows.append(
            {
                "year": year,
                "male": counts["male"],
                "female": counts["female"],
                "male_share": _format_share(counts["male"], row_total),
                "female_share": _format_share(counts["female"], row_total),
                "total": row_total,
            }
        )

    age_distribution_rows = [
        {
            "age_group": label,
            "male": counts["male"],
            "female": counts["female"],
            "male_share": _format_share(counts["male"], counts["male"] + counts["female"] + counts["unspecified"]),
            "female_share": _format_share(counts["female"], counts["male"] + counts["female"] + counts["unspecified"]),
            "total": counts["male"] + counts["female"] + counts["unspecified"],
        }
        for label, counts in age_gender_counts.items()
        if counts["male"] or counts["female"] or counts["unspecified"]
    ]

    return {
        "total_students": total_students,
        "male_count": male_count,
        "female_count": female_count,
        "summary_metrics": {
            "students": total_students,
            "male": male_count,
            "female": female_count,
            "birth_locations": len(location_gender_counts),
        },
        "gender_rows": gender_rows,
        "location_rows": location_rows,
        "location_mix_rows": location_mix_rows,
        "location_map_rows": location_map_rows,
        "location_map_meta": location_map_meta,
        "programme_rows": programme_rows,
        "programme_gender_rows": programme_gender_rows,
        "year_distribution_rows": year_distribution_rows,
        "age_distribution_rows": age_distribution_rows,
    }


def get_demographic_summary_values(request, search_query=""):
    """Calculate demographic summary metrics for asynchronous loading."""

    return build_demographic_data(request, search_query)["summary_metrics"]

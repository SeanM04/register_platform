"""
Drilldown services for demographic charts.
"""

from urllib.parse import urlencode

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse

from dashboard.models import Registration
from dashboard.views import build_registration_filter_q

from .services import (
    DEMOGRAPHIC_CACHE_TTL_SECONDS,
    build_registration_pk_to_progression_year_map,
    _age_group_for_years,
    _calculate_age_from_dob,
)


def _build_drilldown_cache_key(request, chart_key, bucket_key):
    """Cache key scoped to base filters + chart bucket, excluding pagination params."""
    params = {k: v for k, v in request.GET.items() if k not in ("chart", "bucket", "page", "page_size")}
    query_string = urlencode(sorted(params.items()))
    return f"dashboard:demographic:drilldown:{chart_key}:{bucket_key}:{query_string or 'all'}"


def _fetch_unique_drilldown_registrations(request, chart_key, bucket_key):
    """Fetch, deduplicate, and apply secondary filters for a drilldown bucket."""

    combined_filter = build_registration_filter_q(request) & _build_chart_filter(chart_key, bucket_key)
    registrations = (
        Registration.objects.filter(combined_filter)
        .select_related("student", "programme", "programme__department", "programme__department__faculty", "period")
        .order_by("student__registration_number", "-period__external_id", "-id")
    )

    unique_students = {}
    for reg in registrations:
        reg_num = reg.student.registration_number
        if reg_num not in unique_students:
            unique_students[reg_num] = reg

    if chart_key in {"year_distribution", "year_programme"}:
        year_bucket = bucket_key.split("|", 1)[0] if "|" in str(bucket_key) else bucket_key
        try:
            target_year = int(str(year_bucket).strip())
        except (TypeError, ValueError):
            target_year = None
        if target_year is not None and 1 <= target_year <= 5:
            student_ids = {reg.student_id for reg in unique_students.values()}
            reg_year = build_registration_pk_to_progression_year_map(student_ids)
            unique_students = {k: v for k, v in unique_students.items() if reg_year.get(v.id) == target_year}

    if chart_key in {"age_distribution", "age_programme"}:
        age_bucket = bucket_key.split("|", 1)[0] if "|" in str(bucket_key) else bucket_key
        unique_students = {
            k: v for k, v in unique_students.items()
            if _age_group_for_years(_calculate_age_from_dob(v.student.date_of_birth)) == age_bucket
        }

    return list(unique_students.values())


def _get_cached_drilldown_registrations(request, chart_key, bucket_key):
    """Return cached deduplicated registrations for a drilldown bucket."""
    cache_key = _build_drilldown_cache_key(request, chart_key, bucket_key)
    return cache.get_or_set(
        cache_key,
        lambda: _fetch_unique_drilldown_registrations(request, chart_key, bucket_key),
        DEMOGRAPHIC_CACHE_TTL_SECONDS,
    )


def build_demographic_drilldown_data(request, chart_key, bucket_key, page=1, page_size=10):
    """Build drilldown data for demographic charts."""

    unique_registrations = _get_cached_drilldown_registrations(request, chart_key, bucket_key)

    hierarchy_payload = _build_hierarchy_payload(chart_key, bucket_key, unique_registrations)
    if hierarchy_payload:
        hierarchy_payload.update(
            {
                "chart_key": chart_key,
                "bucket_key": bucket_key,
                "bucket_label": _get_bucket_label(chart_key, bucket_key),
                "breadcrumbs": _breadcrumb_items(chart_key, bucket_key),
            }
        )
        return hierarchy_payload
    
    # Paginate
    paginator = Paginator(unique_registrations, page_size)
    page_obj = paginator.get_page(page)
    
    # Build rows
    rows = []
    for reg in page_obj:
        student = reg.student
        
        # Build detail URL
        detail_url = reverse("dashboard:student-detail", args=[student.registration_number.lower()])
        
        # Combine first and last name for display
        full_name = f"{student.first_names} {student.surname}".strip()
        
        row = {
            "name": full_name,
            "gender": student.gender or "Unspecified",
            "place_of_birth": student.place_of_birth or "",
            "programme": reg.programme.name if reg.programme else "Unspecified",
            "programme_code": reg.programme.code if reg.programme else "",
            "department": reg.programme.department.name if reg.programme and reg.programme.department else "",
            "faculty": reg.programme.department.faculty.name if reg.programme and reg.programme.department and reg.programme.department.faculty else "",
            "period": reg.period.name if reg.period else "",
            "detail_url": detail_url,
        }
        rows.append(row)
    
    return {
        "columns": [
            {"key": "name", "label": "Name"},
            {"key": "gender", "label": "Gender"},
            {"key": "place_of_birth", "label": "Place of Birth"},
            {"key": "programme", "label": "Programme"},
            {"key": "department", "label": "Department"},
            {"key": "faculty", "label": "Faculty"},
            {"key": "period", "label": "Period"},
        ],
        "rows": rows,
        "total_count": paginator.count,
        "page": page,
        "page_size": page_size,
        "page_count": paginator.num_pages,
        "chart_key": chart_key,
        "bucket_key": bucket_key,
        "bucket_label": _get_bucket_label(chart_key, bucket_key),
        "title": _get_bucket_label(chart_key, bucket_key),
        "subtitle": "Students filtered by the active dashboard scope.",
        "breadcrumbs": _breadcrumb_items(chart_key, bucket_key),
    }


def _build_chart_filter(chart_key, bucket_key):
    """Build chart-specific filter based on chart type and bucket."""
    
    if chart_key == "gender":
        # bucket_key will be "male", "female", or "unspecified"
        if bucket_key.lower() in ["male", "female"]:
            return Q(student__gender__iexact=bucket_key)
        else:
            return Q(Q(student__gender__isnull=True) | Q(student__gender=""))
    
    elif chart_key == "locations":
        # bucket_key will be a place name
        return Q(student__place_of_birth__icontains=bucket_key)
    
    elif chart_key == "year_distribution":
        # bucket_key will be an academic year as string (e.g., "1", "2", "3", "4", "5")
        try:
            year_int = int(bucket_key)
            # We need to filter by computed academic year
            # This is complex, so we'll handle it with a custom approach
            return Q()  # Will be handled in the query
        except ValueError:
            return Q()
    
    elif chart_key == "age_distribution":
        # bucket_key will be an age group (e.g., "Under 20", "20-24", etc.)
        return Q()  # Will be handled in the query

    elif chart_key == "gender_programme":
        if "|" in bucket_key:
            gender, programme = bucket_key.split("|", 1)
            programme_filter = Q(programme__name__icontains=programme)
            if gender.lower() in ["male", "female"]:
                return programme_filter & Q(student__gender__iexact=gender)
            return programme_filter & (Q(student__gender__isnull=True) | Q(student__gender=""))
        return Q()

    elif chart_key == "location_programme":
        if "|" in bucket_key:
            location, programme = bucket_key.split("|", 1)
            return Q(student__place_of_birth__icontains=location) & Q(programme__name__icontains=programme)
        return Q()

    elif chart_key == "year_programme":
        if "|" in bucket_key:
            _, programme = bucket_key.split("|", 1)
            return Q(programme__name__icontains=programme)
        return Q()

    elif chart_key == "age_programme":
        if "|" in bucket_key:
            _, programme = bucket_key.split("|", 1)
            return Q(programme__name__icontains=programme)
        return Q()
    
    elif chart_key == "programme":
        # bucket_key will be a programme name
        return Q(programme__name__icontains=bucket_key)
    
    elif chart_key == "location_mix":
        # bucket_key will be "location|gender" format
        if "|" in bucket_key:
            location, gender = bucket_key.split("|", 1)
            location_filter = Q(student__place_of_birth__icontains=location)
            if gender.lower() in ["male", "female"]:
                gender_filter = Q(student__gender__iexact=gender)
                return location_filter & gender_filter
            else:
                return location_filter
        else:
            return Q(student__place_of_birth__icontains=bucket_key)
    
    elif chart_key == "programme_gender":
        # bucket_key will be "programme|gender" format
        if "|" in bucket_key:
            programme, gender = bucket_key.split("|", 1)
            programme_filter = Q(programme__name__icontains=programme)
            if gender.lower() in ["male", "female"]:
                gender_filter = Q(student__gender__iexact=gender)
                return programme_filter & gender_filter
            else:
                return programme_filter
        else:
            return Q(programme__name__icontains=bucket_key)
    
    else:
        return Q()


def _build_hierarchy_payload(chart_key, bucket_key, registrations):
    """Return a programme grouping for demographic buckets that support another level."""

    if chart_key not in {"gender", "locations", "year_distribution", "age_distribution"}:
        return None

    grouped = {}
    for registration in registrations:
        programme = registration.programme
        programme_name = programme.normalized_name if programme else "Unspecified programme"
        department = programme.department.name if programme and programme.department else "Unassigned"
        item = grouped.setdefault(
            programme_name,
            {
                "label": programme_name,
                "count": 0,
                "department": department,
                "next_chart": _next_programme_chart(chart_key),
                "next_bucket": f"{bucket_key}|{programme_name}",
            },
        )
        item["count"] += 1

    return {
        "type": "programmes",
        "title": _get_bucket_label(chart_key, bucket_key),
        "subtitle": "Select a programme to view the students in this demographic group.",
        "data": sorted(grouped.values(), key=lambda item: (-item["count"], item["label"])),
    }


def _next_programme_chart(chart_key):
    return {
        "gender": "gender_programme",
        "locations": "location_programme",
        "year_distribution": "year_programme",
        "age_distribution": "age_programme",
    }.get(chart_key, chart_key)


def _breadcrumb_items(chart_key, bucket_key):
    parts = [part.strip() for part in str(bucket_key or "").split("|")]
    items = [{"label": "Demographics", "chart": "", "bucket": ""}]
    if not parts:
        return items

    parent_chart = {
        "gender_programme": "gender",
        "location_programme": "locations",
        "year_programme": "year_distribution",
        "age_programme": "age_distribution",
    }.get(chart_key)

    if parent_chart and len(parts) >= 2:
        items.append({"label": _get_bucket_label(parent_chart, parts[0]), "chart": parent_chart, "bucket": parts[0]})
        items.append({"label": parts[1], "chart": chart_key, "bucket": bucket_key})
        return items

    items.append({"label": _get_bucket_label(chart_key, parts[0]), "chart": chart_key, "bucket": parts[0]})
    return items


def _get_bucket_label(chart_key, bucket_key):
    """Get a human-readable label for the bucket."""
    
    if chart_key == "gender":
        return f"{bucket_key.title()} Students"
    
    elif chart_key == "locations":
        return f"Students from {bucket_key}"
    
    elif chart_key == "year_distribution":
        return f"Year {bucket_key} Students"
    
    elif chart_key == "age_distribution":
        return f"Students in {bucket_key} Age Group"
    
    elif chart_key == "programme":
        return f"Students in {bucket_key}"
    
    elif chart_key == "location_mix":
        if "|" in bucket_key:
            location, gender = bucket_key.split("|", 1)
            return f"{gender.title()} Students from {location}"
        else:
            return f"Students from {bucket_key}"
    
    elif chart_key == "programme_gender":
        if "|" in bucket_key:
            programme, gender = bucket_key.split("|", 1)
            return f"{gender.title()} Students in {programme}"
        else:
            return f"Students in {bucket_key}"

    elif chart_key == "gender_programme":
        if "|" in bucket_key:
            gender, programme = bucket_key.split("|", 1)
            return f"{gender.title()} Students in {programme}"
        return f"Students in {bucket_key}"

    elif chart_key == "location_programme":
        if "|" in bucket_key:
            location, programme = bucket_key.split("|", 1)
            return f"Students from {location} in {programme}"
        return f"Students in {bucket_key}"

    elif chart_key == "year_programme":
        if "|" in bucket_key:
            year, programme = bucket_key.split("|", 1)
            return f"Year {year} Students in {programme}"
        return f"Students in {bucket_key}"

    elif chart_key == "age_programme":
        if "|" in bucket_key:
            age_group, programme = bucket_key.split("|", 1)
            return f"{age_group} Students in {programme}"
        return f"Students in {bucket_key}"
    
    else:
        return f"Students in {bucket_key}"

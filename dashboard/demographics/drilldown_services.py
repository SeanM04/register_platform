"""
Drilldown services for demographic charts.
"""

from django.core.paginator import Paginator
from django.db.models import Q
from dashboard.models import Registration, Student
from dashboard.views import build_registration_filter_q


def build_demographic_drilldown_data(request, chart_key, bucket_key, page=1, page_size=10):
    """Build drilldown data for demographic charts."""
    
    # Get base filter from request
    base_filter = build_registration_filter_q(request)
    
    # Build chart-specific filter
    chart_filter = _build_chart_filter(chart_key, bucket_key)
    
    # Combine filters
    combined_filter = base_filter & chart_filter
    
    # Get registrations with student data, but ensure unique students
    # Use values() with distinct to get one record per student
    registrations = Registration.objects.filter(combined_filter).select_related(
        'student', 'programme', 'programme__department', 'programme__department__faculty', 'period'
    ).order_by('student__registration_number', '-period__external_id', '-id')
    
    # Get unique students by taking the latest registration for each student
    unique_students = {}
    for reg in registrations:
        student_reg_num = reg.student.registration_number
        if student_reg_num not in unique_students:
            unique_students[student_reg_num] = reg
    
    # Convert to list for pagination
    unique_registrations = list(unique_students.values())
    
    # Paginate
    paginator = Paginator(unique_registrations, page_size)
    page_obj = paginator.get_page(page)
    
    # Build rows
    rows = []
    for reg in page_obj:
        student = reg.student
        
        # Build detail URL
        detail_url = f"/students/{student.registration_number}/"
        
        # Combine first and last name for display
        full_name = f"{student.first_names} {student.surname}".strip()
        
        row = {
            "name": full_name,
            "gender": student.gender or "Unspecified",
            "date_of_birth": student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "",
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
            {"key": "date_of_birth", "label": "Date of Birth"},
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
    
    else:
        return f"Students in {bucket_key}"

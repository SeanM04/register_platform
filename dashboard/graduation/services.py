"""Drilldown services for graduation analysis."""

import logging
from urllib.parse import unquote_plus

logger = logging.getLogger(__name__)

def build_graduation_drilldown_data(request, chart_key, bucket_key, page=1, page_size=10):
    """Return student rows for graduation analysis chart drill-downs."""
    
    from ..models import Registration, Student, Programme
    from ..views import build_registration_filter_q
    
    # URL decode the bucket key to handle special characters
    bucket_key = unquote_plus(bucket_key)
    
    try:
        # Build base registration filter
        base_filter = build_registration_filter_q(request)
        registrations = Registration.objects.filter(base_filter)
        
        logger.info(f"Graduation drilldown - chart_key='{chart_key}', bucket_key='{bucket_key}'")
        logger.info(f"Base registrations count: {registrations.count()}")
        
        # For graduation analysis, we'll handle various chart types with specific filtering
        if chart_key == "programme_load":
            # Filter by programme name
            registrations = registrations.filter(programme__name__iexact=bucket_key)
            registrations = registrations.select_related('student', 'programme', 'programme__department')
        elif chart_key == "cohorts":
            # Filter by effective cohort (computed field)
            # Since effective_cohort is computed, we need to filter in Python
            # For cohort drilldown, we should ignore the period filter since the user is selecting a specific period
            from django.db.models import Q
            # Remove period filter from base_filter for cohort drilldown
            base_filter = build_registration_filter_q(request)
            # Remove period-related filters
            base_filter_without_period = Q()
            for child in base_filter.children:
                if not (child[0].startswith('period__') or child[0] == 'period'):
                    base_filter_without_period &= Q(child)
            registrations = Registration.objects.filter(base_filter_without_period)
            registrations = registrations.select_related('student', 'programme', 'programme__department', 'period')
            filtered_registrations = []
            for registration in registrations:
                # Compute effective cohort label similar to graduation service
                cohort_label = f"{registration.period.name}"
                if cohort_label == bucket_key:
                    filtered_registrations.append(registration)
            registrations = filtered_registrations
        elif chart_key == "faculties":
            # Filter by faculty name
            registrations = registrations.filter(programme__department__faculty__name__iexact=bucket_key)
            registrations = registrations.select_related('student', 'programme', 'programme__department')
        elif chart_key == "departments":
            # Filter by department name (hierarchical drilldown from faculty)
            registrations = registrations.filter(programme__department__name__iexact=bucket_key)
            registrations = registrations.select_related('student', 'programme', 'programme__department', 'programme__department__faculty')
        elif chart_key == "programmes":
            # Filter by programme name (hierarchical drilldown from department)
            registrations = registrations.filter(programme__name__iexact=bucket_key)
            registrations = registrations.select_related('student', 'programme', 'programme__department', 'programme__department__faculty')
        else:
            # Default case - return all filtered registrations
            registrations = registrations.select_related('student', 'programme', 'programme__department')
        
        logger.info(f"Filtered registrations count: {len(registrations) if isinstance(registrations, list) else registrations.count()}")
        
        # Get total count for pagination
        if isinstance(registrations, list):
            total_count = len(registrations)
        else:
            total_count = registrations.count()
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        
        # Apply pagination
        offset = (page - 1) * page_size
        if isinstance(registrations, list):
            paginated_registrations = registrations[offset:offset + page_size]
        else:
            paginated_registrations = registrations[offset:offset + page_size]
        
        # Build student rows
        student_rows = []
        for registration in paginated_registrations:
            student = registration.student
            programme = registration.programme
            row_data = {
                "name": student.full_name,
                "registration_number": student.registration_number,
                "programme": programme.name if programme else "Unassigned",
                "department": programme.department.name if programme and programme.department else "Unassigned",
                "faculty": programme.department.faculty.name if programme and programme.department and programme.department.faculty else "Unassigned",
                "decision": registration.decision or "Unknown",
                "carrying": registration.carrying or 0,
                "detail_url": f"/students/{student.registration_number}/",
            }
            student_rows.append(row_data)
        
        # Build response payload
        payload = {
            "title": f"Students - {bucket_key}",
            "subtitle": f"Students for {chart_key}: {bucket_key}",
            "columns": [
                {"key": "name", "label": "Student Name"},
                {"key": "registration_number", "label": "Registration Number"},
                {"key": "programme", "label": "Programme"},
                {"key": "department", "label": "Department"},
                {"key": "faculty", "label": "Faculty"},
                {"key": "decision", "label": "Decision"},
                {"key": "carrying", "label": "Carrying"},
            ],
            "rows": student_rows,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_items": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1,
            },
        }
        
        return payload
        
    except Exception as e:
        logger.error(f"Error in build_graduation_drilldown_data: {e}")
        raise

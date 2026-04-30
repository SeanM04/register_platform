"""Drilldown services for graduation analysis."""

import logging
from urllib.parse import unquote_plus

logger = logging.getLogger(__name__)

def build_graduation_drilldown_data(request, chart_key, bucket_key, page=1, page_size=10):
    """Return student rows for graduation analysis chart drill-downs."""
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Graduation drilldown called: chart_key={chart_key}, bucket_key={bucket_key}, page={page}")
    
    try:
        # Get filter parameters from request
        year = request.GET.get('year')
        period = request.GET.get('period')
        faculty = request.GET.get('faculty')
        
        logger.info(f"Graduation drilldown - chart_key='{chart_key}', bucket_key='{bucket_key}'")
        logger.info(f"Filters: year={year}, period={period}, faculty={faculty}")
        
        # Use the same graduation service logic as the charts
        try:
            import time
            start_time = time.time()
            
            from services.graduation_services import get_graduation_page_data
            graduation_data = get_graduation_page_data(year=year, period=period, faculty=faculty)
            
            service_time = time.time() - start_time
            logger.info(f"Graduation service took {service_time:.2f} seconds")
            
            # Get the graduated students from the service
            graduated_students = graduation_data["students"]
            logger.info(f"Total graduated students from service: {len(graduated_students)}")
        except Exception as e:
            logger.error(f"Error calling graduation service: {e}")
            raise
        
        # Filter graduated students based on chart_key and bucket_key
        filtered_students = []
        
        if chart_key == "faculties":
            # Filter by faculty name
            filtered_students = [
                student for student in graduated_students 
                if student["faculty"] == bucket_key
            ]
        elif chart_key == "departments":
            # Filter by department name
            filtered_students = [
                student for student in graduated_students 
                if student.get("department_name") == bucket_key
            ]
        elif chart_key == "programmes" or chart_key == "programme_load":
            # Filter by programme name
            filtered_students = [
                student for student in graduated_students 
                if student["programme_name"] == bucket_key
            ]
        elif chart_key == "cohorts":
            # Filter by cohort
            filtered_students = [
                student for student in graduated_students 
                if student["effective_cohort"] == bucket_key or student["original_cohort"] == bucket_key
            ]
        elif chart_key == "timing":
            # Filter by graduation timing (on-time vs delayed)
            filtered_students = [
                student for student in graduated_students 
                if (bucket_key == "On-time" and student.get("on_time", False)) or
                   (bucket_key == "Delayed" and not student.get("on_time", False))
            ]
        else:
            # Default case - return all graduated students
            filtered_students = graduated_students
        
        logger.info(f"Filtered students count: {len(filtered_students)}")
        
        # Apply pagination to filtered students
        total_count = len(filtered_students)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        
        offset = (page - 1) * page_size
        paginated_students = filtered_students[offset:offset + page_size]
        
        # Build student rows from paginated graduated students
        student_rows = []
        for student in paginated_students:
            # Try to get department name from programme if student record doesn't have it
            department_name = student.get("department_name", "Unknown")
            if department_name == "Unknown" or not department_name:
                try:
                    from dashboard.models import Programme
                    prog_name = student["programme_name"]
                    
                    # Try exact match first
                    programme = Programme.objects.filter(name=prog_name).first()
                    
                    # If not found, try case-insensitive match
                    if not programme:
                        programme = Programme.objects.filter(name__iexact=prog_name).first()
                    
                    # If still not found, try normalized matching (handle & vs "and")
                    if not programme:
                        normalized_name = prog_name.replace('&', 'and').replace('  ', ' ').strip()
                        programme = Programme.objects.filter(name__iexact=normalized_name).first()
                    
                    # Final fallback: try partial matching on key words
                    if not programme:
                        # Extract key parts (degree and main subject)
                        parts = prog_name.split()
                        if len(parts) >= 3:
                            # Try matching on the main subject part
                            subject_parts = parts[2:]  # Skip degree and first word
                            for i in range(1, len(subject_parts) + 1):
                                partial = ' '.join(subject_parts[:i])
                                programme = Programme.objects.filter(name__icontains=partial).first()
                                if programme:
                                    break
                    
                    if programme and programme.department:
                        department_name = programme.department.name
                        logger.info(f"Matched '{prog_name}' to '{programme.name}' -> {department_name}")
                    else:
                        department_name = "Unassigned"
                        logger.warning(f"Could not find department for programme: {prog_name}")
                        
                except Exception as e:
                    logger.warning(f"Could not get department for programme {student['programme_name']}: {e}")
                    department_name = "Unassigned"
            
            # Only log if department was successfully resolved from programme
            if department_name != "Unassigned" and student.get("department_name", "Unknown") == "Unknown":
                logger.info(f"Resolved department for {student['student_name']}: {department_name}")
            
            row_data = {
                "name": student["student_name"],
                "programme": student["programme_name"],
                "department": department_name,
                "faculty": student["faculty"],
                "decision": "Graduated",
                "carrying": 0,
                "detail_url": f"/students/{student['regnum'].lower()}/",
            }
            student_rows.append(row_data)
        
        # Build response payload
        payload = {
            "title": f"Students - {bucket_key}",
            "subtitle": f"Students for {chart_key}: {bucket_key}",
            "columns": [
                {"key": "name", "label": "Student Name"},
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

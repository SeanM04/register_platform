from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import logging
import json

from accounts.decorators import login_required_except_domains
from ..views import build_layout_context
from .json_encoder import PandasJSONEncoder

logger = logging.getLogger(__name__)

COMPLETION_ACTIVE_KEY = "completion"
COMPLETION_PAGE_TITLE = "Completion Analysis"


@login_required_except_domains()
@require_GET
def completion_view(request):
    """
    Render the completion analysis page.
    """
    context = build_layout_context(request, COMPLETION_ACTIVE_KEY)
    context.update({
        "page_title": COMPLETION_PAGE_TITLE,
    })
    return render(request, 'dashboard/completion.html', context)


@require_GET
def completion_payload(request):
    """
    Return completion analysis data as JSON.
    This endpoint provides data for frontend completion analysis page.
    """
    try:
        # Get topbar filter parameters
        year = request.GET.get('year')
        period = request.GET.get('period')
        faculty = request.GET.get('faculty')
        
        # Call the completion service
        from services.completion_service import get_completion_page_data
        
        data = get_completion_page_data(
            year=year,
            period=period,
            faculty=faculty
        )
        
        return JsonResponse({
            'status': 'success',
            'data': data
        }, encoder=PandasJSONEncoder)
        
    except Exception as e:
        logger.error(f"Error in completion_payload: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_GET
def completion_programmes(request):
    """
    Return list of available programmes for completion analysis.
    """
    try:
        from services.completion_service import get_completion_programmes
        
        programmes = get_completion_programmes()
        
        return JsonResponse({
            'status': 'success',
            'programmes': programmes
        })
        
    except Exception as e:
        logger.error(f"Error in completion_programmes: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_GET
def completion_faculties(request):
    """
    Return list of available faculties for completion analysis.
    """
    try:
        from services.completion_service import get_completion_faculties
        
        faculties = get_completion_faculties()
        
        return JsonResponse({
            'status': 'success',
            'faculties': faculties
        })
        
    except Exception as e:
        logger.error(f"Error in completion_faculties: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_GET
def completion_academic_years(request):
    """
    Return list of available academic years for completion analysis.
    """
    try:
        from services.completion_service import get_completion_academic_years
        
        years = get_completion_academic_years()
        
        return JsonResponse({
            'status': 'success',
            'years': years
        })
        
    except Exception as e:
        logger.error(f"Error in completion_academic_years: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_GET
def completion_periods(request):
    """
    Return list of available periods for completion analysis.
    """
    try:
        from services.completion_service import get_completion_periods
        
        periods = get_completion_periods()
        
        return JsonResponse({
            'status': 'success',
            'periods': periods
        })
        
    except Exception as e:
        logger.error(f"Error in completion_periods: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_GET
def completion_periods_by_year(request):
    """
    Return list of available periods grouped by academic year for completion analysis.
    """
    try:
        from services.completion_service import get_completion_periods_by_year
        
        periods_by_year = get_completion_periods_by_year()
        
        return JsonResponse({
            'status': 'success',
            'periods_by_year': periods_by_year
        })
        
    except Exception as e:
        logger.error(f"Error in completion_periods_by_year: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

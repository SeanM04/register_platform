from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import logging
import json

from accounts.decorators import login_required_except_domains
from ..views import build_layout_context
from .json_encoder import PandasJSONEncoder

logger = logging.getLogger(__name__)

GRADUATION_ACTIVE_KEY = "graduation"
GRADUATION_PAGE_TITLE = "Graduation Analysis"


@login_required_except_domains()
@require_GET
def graduation_view(request):
    """
    Render the graduation analysis page.
    """
    context = build_layout_context(request, GRADUATION_ACTIVE_KEY)
    context.update({
        "page_title": GRADUATION_PAGE_TITLE,
    })
    return render(request, 'dashboard/graduation.html', context)


@require_GET
def graduation_payload(request):
    """
    Return graduation analysis data as JSON.
    This endpoint provides data for frontend graduation analysis page.
    """
    try:
        # Get topbar filter parameters
        year = request.GET.get('year')
        period = request.GET.get('period')
        faculty = request.GET.get('faculty')
        
        # Call graduation service
        from services.graduation_services import get_graduation_page_data
        
        data = get_graduation_page_data(
            year=year,
            period=period,
            faculty=faculty,
        )
        
        return JsonResponse({
            'status': 'success',
            'data': data
        }, encoder=PandasJSONEncoder)
        
    except Exception as e:
        logger.error(f"Error in graduation_payload: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_GET
def graduation_programmes(request):
    """
    Return list of available programmes for graduation analysis.
    """
    try:
        from services.graduation_services import get_graduation_programmes
        
        programmes = get_graduation_programmes()
        
        return JsonResponse({
            'status': 'success',
            'programmes': programmes
        })
        
    except Exception as e:
        logger.error(f"Error in graduation_programmes: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_GET
def graduation_faculties(request):
    """
    Return list of available faculties for graduation analysis.
    """
    try:
        from services.graduation_services import get_graduation_faculties
        
        faculties = get_graduation_faculties()
        
        return JsonResponse({
            'status': 'success',
            'faculties': faculties
        })
        
    except Exception as e:
        logger.error(f"Error in graduation_faculties: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

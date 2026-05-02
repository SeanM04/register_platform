from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import logging
import json

from django.conf import settings

from accounts.decorators import login_required_except_domains
from ..views import build_layout_context
from .json_encoder import PandasJSONEncoder

logger = logging.getLogger(__name__)

GRADUATION_ACTIVE_KEY = "graduation"
GRADUATION_PAGE_TITLE = "Graduation Analysis"


def _graduation_ai_narratives_enabled():
    """Return whether an AI provider is available for graduation narratives."""

    provider = getattr(settings, "AI_INSIGHTS_PROVIDER", "auto").strip().lower()
    insights_enabled = bool(
        getattr(settings, "AI_INSIGHTS_ENABLED", False)
        or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False)
    )
    if provider == "rules" or not insights_enabled:
        return False

    google_ready = provider in {"auto", "google"} and bool(getattr(settings, "GOOGLE_API_KEY", ""))
    openai_ready = (
        provider in {"auto", "openai"}
        and bool(getattr(settings, "OPENAI_API_KEY", ""))
        and (provider == "openai" or getattr(settings, "OPENAI_INSIGHTS_ENABLED", False))
    )
    return google_ready or openai_ready


@login_required_except_domains()
@require_GET
def graduation_view(request):
    """
    Render the graduation analysis page.
    """
    context = build_layout_context(request, GRADUATION_ACTIVE_KEY)
    context.update({
        "page_title": GRADUATION_PAGE_TITLE,
        "graduation_ai_narratives_enabled": _graduation_ai_narratives_enabled(),
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
def graduation_narratives(request):
    """
    Return optional AI or rule-based narratives for the graduation page.
    """
    try:
        year = request.GET.get('year')
        period = request.GET.get('period')
        faculty = request.GET.get('faculty')

        from services.graduation_services import get_graduation_page_data
        from .ai_insights import get_graduation_card_narratives_result

        graduation_data = get_graduation_page_data(
            year=year,
            period=period,
            faculty=faculty,
        )

        return JsonResponse(get_graduation_card_narratives_result(graduation_data))

    except Exception as e:
        logger.error(f"Error in graduation_narratives: {e}")
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


@require_GET
def graduation_drilldown(request):
    """
    Return drilldown data for graduation analysis charts.
    Supports hierarchical navigation: Faculty → Department → Programme → Students
    """
    import time
    start_time = time.time()
    
    try:
        from urllib.parse import unquote_plus
        from .services import build_graduation_drilldown_data
        
        # Get drilldown parameters
        chart_key = request.GET.get('chart_key', '')
        bucket_key = unquote_plus(request.GET.get('bucket_key', ''))
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        logger.info(f"Graduation drilldown request: chart_key={chart_key}, bucket_key={bucket_key}, page={page}")
        
        # Build drilldown payload using optimized graduation service
        try:
            from .drilldown_optimized import build_optimized_graduation_drilldown_data
            payload = build_optimized_graduation_drilldown_data(
                request=request,
                chart_key=chart_key,
                bucket_key=bucket_key,
                page=page,
                page_size=page_size
            )
            logger.info("Using optimized graduation drilldown service")
        except ImportError:
            # Fallback to original service if optimized version not available
            from .services import build_graduation_drilldown_data
            payload = build_graduation_drilldown_data(
                request=request,
                chart_key=chart_key,
                bucket_key=bucket_key,
                page=page,
                page_size=page_size
            )
            logger.info("Using original graduation drilldown service")
        
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Graduation drilldown completed in {duration:.2f} seconds")
        
        return JsonResponse({
            'status': 'success',
            'data': payload
        })
        
    except Exception as e:
        logger.error(f"Error in graduation_drilldown: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

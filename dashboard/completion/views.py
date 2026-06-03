from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import logging
import json

from django.conf import settings

from accounts.decorators import login_required_except_domains
from ..views import build_layout_context, build_summary_cards
from .json_encoder import PandasJSONEncoder

logger = logging.getLogger(__name__)

COMPLETION_ACTIVE_KEY = "completion"
COMPLETION_PAGE_TITLE = "Completion Analysis"
COMPLETION_SUMMARY_CARD_SPECS = [
    {"key": "total_students", "label": "Total Students", "tone": "default"},
    {"key": "total_cohorts", "label": "Effective Cohorts", "tone": "default"},
    {"key": "average_completion_rate", "label": "Average Completion", "tone": "default"},
    {"key": "zero_completion_students", "label": "Zero Completion", "tone": "danger"},
    {"key": "shifted_students", "label": "Shifted Students", "tone": "default"},
]
COMPLETION_SUMMARY_CARD_NOTES = {
    "total_students": "Unique students currently visible in this scope.",
    "total_cohorts": "Cohorts contributing to the completion analysis.",
    "average_completion_rate": "Average completion across the visible cohort set.",
    "zero_completion_students": "Students forced to 0% under the completion rules.",
    "shifted_students": "Students moved into a later effective cohort.",
}


def _completion_ai_narratives_enabled():
    """Return whether an AI provider is available for completion narratives."""

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
def completion_view(request):
    """
    Render the completion analysis page.
    """
    context = build_layout_context(request, COMPLETION_ACTIVE_KEY)
    context.update({
        "page_title": COMPLETION_PAGE_TITLE,
        "completion_ai_narratives_enabled": _completion_ai_narratives_enabled(),
        "summary_cards": build_summary_cards(
            COMPLETION_SUMMARY_CARD_SPECS,
            notes=COMPLETION_SUMMARY_CARD_NOTES,
        ),
    })
    return render(request, 'dashboard/completion.html', context)


@require_GET
def completion_metrics(request):
    """
    Return fast KPI counts for the completion dashboard before the full payload arrives.
    """
    try:
        from services.completion_service import get_cached_completion_fast_kpis
        result = get_cached_completion_fast_kpis(
            year=request.GET.get('year'),
            period=request.GET.get('period'),
            faculty=request.GET.get('faculty'),
        )
        metrics = result.get("kpis", {})
        return JsonResponse({
            **result,
            "summary_cards": build_summary_cards(
                COMPLETION_SUMMARY_CARD_SPECS,
                metrics,
                COMPLETION_SUMMARY_CARD_NOTES,
            ),
        })
    except Exception as e:
        logger.error(f"Error in completion_metrics: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_GET
def completion_payload(request):
    """
    Return completion analysis data as JSON.
    This endpoint provides data for frontend completion analysis page.
    """
    try:
        from services.completion_service import get_cached_completion_page_data
        data = get_cached_completion_page_data(
            year=request.GET.get('year'),
            period=request.GET.get('period'),
            faculty=request.GET.get('faculty'),
        )
        metrics = data.get("kpis", {})
        data["summary_cards"] = build_summary_cards(
            COMPLETION_SUMMARY_CARD_SPECS,
            metrics,
            COMPLETION_SUMMARY_CARD_NOTES,
        )
        return JsonResponse({'status': 'success', 'data': data}, encoder=PandasJSONEncoder)
    except Exception as e:
        logger.error(f"Error in completion_payload: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_GET
def completion_narratives(request):
    """
    Return optional AI or rule-based narratives for the completion page.
    """
    try:
        year = request.GET.get('year')
        period = request.GET.get('period')
        faculty = request.GET.get('faculty')

        from services.completion_service import get_cached_completion_page_data
        from .ai_insights import get_completion_card_narratives_result

        completion_data = get_cached_completion_page_data(
            year=year,
            period=period,
            faculty=faculty,
        )

        return JsonResponse(get_completion_card_narratives_result(completion_data))

    except Exception as e:
        logger.error(f"Error in completion_narratives: {e}")
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


@require_GET
def completion_drilldown(request):
    """
    Return drilldown data for completion analysis charts.
    Supports hierarchical navigation: Faculty → Department → Programme → Students
    """
    try:
        from urllib.parse import unquote_plus
        from .services import build_completion_drilldown_data
        
        # Get drilldown parameters
        chart_key = request.GET.get('chart_key', '')
        bucket_key = unquote_plus(request.GET.get('bucket_key', ''))
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        # Build drilldown payload using completion service
        payload = build_completion_drilldown_data(
            request=request,
            chart_key=chart_key,
            bucket_key=bucket_key,
            page=page,
            page_size=page_size
        )
        
        return JsonResponse({
            'status': 'success',
            'data': payload
        })
        
    except Exception as e:
        logger.error(f"Error in completion_drilldown: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

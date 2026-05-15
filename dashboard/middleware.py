import logging
import traceback as tb_module

logger = logging.getLogger(__name__)


class ErrorLoggingMiddleware:
    """Catches unhandled exceptions during request processing and persists them to ErrorLog."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        try:
            from .models import ErrorLog
            ErrorLog.from_request(request, exception, tb_module.format_exc())
        except Exception:
            # Never let the logger itself crash the response — fall back to console.
            logger.exception("ErrorLoggingMiddleware failed to write to DB")
        return None  # Let Django's normal exception handling continue

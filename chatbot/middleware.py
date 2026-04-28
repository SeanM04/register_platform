"""
Chatbot rate limiting middleware.

Applies a per-user sliding-window rate limit to all chatbot POST endpoints.
Returns HTTP 429 with a Retry-After header when the limit is exceeded.

Configuration (via settings.py or environment variables):
    CHATBOT_RATE_LIMIT_REQUESTS        int  default 30
    CHATBOT_RATE_LIMIT_WINDOW_SECONDS  int  default 60

The limit is tracked per authenticated user using Django's cache backend.
LocMemCache (the default) works correctly for a single-process server.
For multi-process/multi-worker deployments, configure a shared cache backend
(e.g. Redis via django-redis) so all workers share the same counters.
"""

import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

# Paths this middleware guards (both the plain JSON and the SSE stream endpoint)
_GUARDED_PATHS = frozenset({
    "/api/chatbot/message/",
    "/api/chatbot/stream/",
})

_LIMIT: int = getattr(settings, "CHATBOT_RATE_LIMIT_REQUESTS", 30)
_WINDOW: int = getattr(settings, "CHATBOT_RATE_LIMIT_WINDOW_SECONDS", 60)


class ChatbotRateLimitMiddleware:
    """
    Sliding-window rate limiter for chatbot endpoints.

    Each authenticated user gets a list of request timestamps stored in the
    cache.  Timestamps older than the window are pruned on every request, so
    the window truly slides rather than resetting on a fixed boundary.

    Unauthenticated requests are passed through — they will hit the view's
    @ajax_login_required check and return 401 there.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path in _GUARDED_PATHS:
            rejection = _check_rate_limit(request)
            if rejection is not None:
                return rejection
        return self.get_response(request)


def _check_rate_limit(request) -> JsonResponse | None:
    """Return a 429 JsonResponse if the user has exceeded their limit, else None."""
    if not request.user.is_authenticated:
        return None

    now = time.time()
    cache_key = f"chatbot_rl:{request.user.pk}"

    # Load existing timestamps, prune those outside the current window
    timestamps: list[float] = cache.get(cache_key) or []
    cutoff = now - _WINDOW
    timestamps = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= _LIMIT:
        # Time until the oldest recorded request falls outside the window
        retry_after = max(1, int(_WINDOW - (now - timestamps[0])) + 1)
        plural = "" if retry_after == 1 else "s"
        resp = JsonResponse(
            {
                "error": (
                    f"You're sending messages too quickly. "
                    f"Please wait {retry_after} second{plural} before trying again."
                ),
                "retry_after": retry_after,
            },
            status=429,
        )
        resp["Retry-After"] = str(retry_after)
        return resp

    # Record this request and save back to cache
    timestamps.append(now)
    cache.set(cache_key, timestamps, timeout=_WINDOW)
    return None

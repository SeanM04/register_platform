"""Custom decorators for authenticated dashboard endpoints."""

from functools import wraps

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def is_platform_admin(user):
    """Return True when the authenticated user can access platform management features."""

    if not user or not user.is_authenticated:
        return False

    user_type_code = getattr(getattr(user, "user_type", None), "code", "")
    return bool(user.is_superuser or user.is_staff or user_type_code == "admin")


def ajax_login_required(view_func):
    """Return HTTP 401 JSON when an AJAX/JSON endpoint is unauthenticated.

    Works with both sync and async views — the wrapper returned matches the
    coroutine-function status of the wrapped view so Django's ASGI handler
    treats it correctly.
    """
    if iscoroutinefunction(view_func):
        @wraps(view_func)
        async def _async_wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Authentication required."}, status=401)
            return await view_func(request, *args, **kwargs)

        markcoroutinefunction(_async_wrapped)
        return _async_wrapped

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped


def login_required_except_domains(allowed_domains=None):
    """Require authentication unless the request host is explicitly allowed."""

    allowed = set(allowed_domains or getattr(settings, "LOGIN_BYPASS_DOMAINS", []))

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            host = request.get_host().split(":")[0].lower()
            if host in allowed:
                return view_func(request, *args, **kwargs)
            if not request.user.is_authenticated:
                login_path = reverse(settings.LOGIN_URL)
                return redirect(f"{login_path}?next={request.get_full_path()}")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def platform_admin_required(view_func):
    """Require an authenticated platform administrator for sensitive management views."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_path = reverse(settings.LOGIN_URL)
            return redirect(f"{login_path}?next={request.get_full_path()}")
        if not is_platform_admin(request.user):
            raise PermissionDenied("You do not have access to system management.")
        return view_func(request, *args, **kwargs)

    return _wrapped

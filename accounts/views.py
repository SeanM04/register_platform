"""Authentication views for login, logout, and protected AJAX endpoints."""

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.shortcuts import redirect, render, resolve_url
from django.views.decorators.http import require_http_methods

from dashboard.models import AuditLog
from .decorators import ajax_login_required
from .services import initialize_user_session


@login_not_required
@require_http_methods(["GET", "POST"])
def login_view(request):
    """Render the login page on GET and authenticate users on POST."""

    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return render(request, "accounts/login.html", {"next": request.GET.get("next", "")})

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    next_url = request.POST.get("next") or settings.LOGIN_REDIRECT_URL

    if not username or not password:
        return JsonResponse({"error": "Username and password are required."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        initialize_user_session(request, user)
        AuditLog.record(
            AuditLog.ACTION_LOGIN_SUCCESS, actor=user, target_email=user.email, request=request
        )
        return JsonResponse({"redirect": resolve_url(next_url)})

    if getattr(request, "lockout_info", None):
        AuditLog.record(
            AuditLog.ACTION_LOGIN_FAILED,
            target_email=username,
            detail={"reason": "account_locked"},
            request=request,
        )
        return JsonResponse({"lockout_info": request.lockout_info}, status=423)
    if getattr(request, "login_error", "") == "inactive_user":
        AuditLog.record(
            AuditLog.ACTION_LOGIN_FAILED,
            target_email=username,
            detail={"reason": "inactive_account"},
            request=request,
        )
        return JsonResponse({"error": "This account is inactive."}, status=403)

    AuditLog.record(
        AuditLog.ACTION_LOGIN_FAILED,
        target_email=username,
        detail={"reason": "invalid_credentials"},
        request=request,
    )
    return JsonResponse({"error": "Invalid username or password."}, status=401)


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """Log the user out and redirect to the login page."""

    if request.user.is_authenticated:
        AuditLog.record(
            AuditLog.ACTION_LOGOUT, actor=request.user, target_email=request.user.email, request=request
        )
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@ajax_login_required
def auth_ping(request):
    """Simple protected AJAX endpoint used for validation and tests."""

    return JsonResponse({"status": "ok"})

"""Middleware for validating critical authentication session state."""

from django.conf import settings
from django.contrib.auth import logout
from django.urls import reverse
from django.shortcuts import redirect

from .services import SESSION_EMAIL_KEY, SESSION_LOGIN_AT_KEY, SESSION_ROLE_KEY, initialize_user_session


class SessionValidationMiddleware:
    """Ensure authenticated requests have valid session metadata."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            login_path = reverse(settings.LOGIN_URL)
            logout_path = reverse("logout")
            exempt_prefixes = (
                login_path,
                logout_path,
                "/auth/",
                "/admin/login/",
            )
            if not any(request.path.startswith(prefix) for prefix in exempt_prefixes):
                expected_email = request.user.email
                session_email = request.session.get(SESSION_EMAIL_KEY)
                session_role = request.session.get(SESSION_ROLE_KEY)
                expected_role = request.user.user_type.code if request.user.user_type else ""

                if session_email is None or SESSION_LOGIN_AT_KEY not in request.session:
                    initialize_user_session(request, request.user)
                elif session_email != expected_email or session_role != expected_role:
                    logout(request)
                    return redirect(f"{login_path}?next={request.get_full_path()}")

        return self.get_response(request)

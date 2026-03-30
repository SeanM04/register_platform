"""Authentication backends for the accounts app."""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

from .services import (
    check_current_lockout,
    get_client_ip,
    get_tenant_name,
    increment_failed_attempts,
    normalize_identifier,
    reset_lockouts,
)


class LockoutBackend(ModelBackend):
    """Authenticate users while enforcing lockouts by email and IP address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        identifier = normalize_identifier(username or kwargs.get(user_model.USERNAME_FIELD))
        if not identifier or not password:
            return None

        ip_address = get_client_ip(request)
        tenant_name = get_tenant_name(request)

        lockout_info = check_current_lockout(identifier, ip_address, tenant_name)
        if lockout_info:
            if request is not None:
                request.lockout_info = lockout_info
            return None

        try:
            user = user_model.objects.get(email__iexact=identifier)
        except user_model.DoesNotExist:
            lockout_info = increment_failed_attempts(identifier, ip_address, tenant_name)
            if request is not None:
                request.login_error = "invalid_credentials"
                if lockout_info:
                    request.lockout_info = lockout_info
            user_model().set_password(password)
            return None

        if not user.check_password(password):
            lockout_info = increment_failed_attempts(identifier, ip_address, tenant_name)
            if request is not None:
                request.login_error = "invalid_credentials"
                if lockout_info:
                    request.lockout_info = lockout_info
            return None

        if not self.user_can_authenticate(user):
            if request is not None:
                request.login_error = "inactive_user"
            return None

        reset_lockouts(identifier, ip_address, tenant_name)
        return user

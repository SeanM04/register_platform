"""Authentication support services such as lockout handling and session state."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginLockout


SESSION_ROLE_KEY = "auth_user_role"
SESSION_EMAIL_KEY = "auth_user_email"
SESSION_LOGIN_AT_KEY = "auth_login_at"


def get_client_ip(request):
    """Return the best-effort client IP address for the current request."""

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def get_tenant_name(request):
    """Return the host name as a simple tenant/site identifier."""

    if not request:
        return ""
    return request.get_host().split(":")[0].strip().lower()


def normalize_identifier(identifier):
    """Normalize email/username input for lockout lookups."""

    return (identifier or "").strip().lower()


def _lockout_duration():
    return timedelta(minutes=getattr(settings, "AUTH_LOCKOUT_DURATION_MINUTES", 15))


def _failure_limit():
    return getattr(settings, "AUTH_LOCKOUT_FAILURE_LIMIT", 5)


def expire_lockouts(identifier=None, ip_address=None, tenant_name=""):
    """Expire outdated lockouts and return the number of reset records."""

    queryset = LoginLockout.objects.filter(is_locked=True, locked_until__lte=timezone.now())
    if identifier is not None:
        queryset = queryset.filter(identifier=normalize_identifier(identifier))
    if ip_address is not None:
        queryset = queryset.filter(ip_address=ip_address)
    if tenant_name:
        queryset = queryset.filter(tenant_name=tenant_name)

    updated = queryset.update(
        is_locked=False,
        locked_at=None,
        locked_until=None,
        attempt_count=0,
    )
    return updated


def _serialize_lockout(record):
    return {
        "identifier": record.identifier,
        "ip_address": record.ip_address,
        "tenant_name": record.tenant_name,
        "attempt_count": record.attempt_count,
        "locked_until": record.locked_until.isoformat() if record.locked_until else None,
    }


def check_current_lockout(identifier, ip_address, tenant_name=""):
    """Return lockout details for the current request scope if locked."""

    normalized_identifier = normalize_identifier(identifier)
    expire_lockouts(identifier=normalized_identifier, ip_address=ip_address, tenant_name=tenant_name)
    expire_lockouts(identifier="", ip_address=ip_address, tenant_name=tenant_name)

    scoped_records = LoginLockout.objects.filter(
        tenant_name=tenant_name,
        ip_address=ip_address,
        is_locked=True,
        locked_until__gt=timezone.now(),
    ).filter(identifier__in=[normalized_identifier, ""])

    record = scoped_records.order_by("-locked_until").first()
    return _serialize_lockout(record) if record else None


def increment_failed_attempts(identifier, ip_address, tenant_name=""):
    """Increment failure counters and lock the scope when the threshold is reached."""

    normalized_identifier = normalize_identifier(identifier)
    lockout_info = None
    for scope_identifier in [normalized_identifier, ""]:
        record, _ = LoginLockout.objects.get_or_create(
            ip_address=ip_address,
            identifier=scope_identifier,
            tenant_name=tenant_name,
            defaults={"attempt_count": 0},
        )
        record.attempt_count += 1
        if record.attempt_count >= _failure_limit():
            record.is_locked = True
            record.locked_at = timezone.now()
            record.locked_until = timezone.now() + _lockout_duration()
            lockout_info = _serialize_lockout(record)
        record.save(update_fields=["attempt_count", "is_locked", "locked_at", "locked_until", "updated_at"])

    return lockout_info


def reset_lockouts(identifier, ip_address, tenant_name=""):
    """Clear lockout state after a successful login."""

    normalized_identifier = normalize_identifier(identifier)
    LoginLockout.objects.filter(
        ip_address=ip_address,
        tenant_name=tenant_name,
        identifier__in=[normalized_identifier, ""],
    ).update(
        attempt_count=0,
        is_locked=False,
        locked_at=None,
        locked_until=None,
    )


def initialize_user_session(request, user):
    """Store the required authentication session metadata."""

    request.session[SESSION_EMAIL_KEY] = user.email
    request.session[SESSION_ROLE_KEY] = user.user_type.code if user.user_type else ""
    request.session[SESSION_LOGIN_AT_KEY] = timezone.now().isoformat()

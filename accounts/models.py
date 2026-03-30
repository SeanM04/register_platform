"""Authentication and authorization models."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import UserManager


class TimeStampedModel(models.Model):
    """Reusable created/updated timestamp fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserType(TimeStampedModel):
    """Role catalogue for authenticated users."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Custom user model that authenticates with email instead of username."""

    username = None
    email = models.EmailField(unique=True)
    user_type = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email


class LoginLockout(TimeStampedModel):
    """Tracks failed login attempts and active lockouts by identifier and IP."""

    ip_address = models.GenericIPAddressField()
    identifier = models.CharField(max_length=255, blank=True)
    tenant_name = models.CharField(max_length=255, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [("ip_address", "identifier", "tenant_name")]

    def __str__(self):
        scope = self.identifier or "ip-only"
        return f"{scope} @ {self.ip_address}"

    @property
    def is_currently_locked(self):
        return self.is_locked and self.locked_until and self.locked_until > timezone.now()

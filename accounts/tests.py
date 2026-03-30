"""Authentication system tests."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import LoginLockout, UserType
from .services import SESSION_EMAIL_KEY, SESSION_LOGIN_AT_KEY, SESSION_ROLE_KEY


@override_settings(
    AUTH_LOCKOUT_FAILURE_LIMIT=3,
    AUTH_LOCKOUT_DURATION_MINUTES=30,
)
class AuthenticationTests(TestCase):
    """End-to-end tests for the custom authentication flow."""

    def setUp(self):
        self.client = Client()
        self.user_type, _ = UserType.objects.get_or_create(
            code="admin",
            defaults={"name": "Admin"},
        )
        self.user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="StrongPass123!",
            first_name="Admin",
            last_name="User",
            user_type=self.user_type,
            is_active=True,
        )

    def test_successful_login(self):
        response = self.client.post(
            reverse("login"),
            {"username": "admin@example.com", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect"], reverse("dashboard:home"))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.session[SESSION_EMAIL_KEY], "admin@example.com")
        self.assertEqual(self.client.session[SESSION_ROLE_KEY], "admin")
        self.assertIn(SESSION_LOGIN_AT_KEY, self.client.session)

    def test_invalid_password(self):
        response = self.client.post(
            reverse("login"),
            {"username": "admin@example.com", "password": "WrongPass123!"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Invalid username or password.")

    def test_lockout_after_repeated_failed_attempts(self):
        for _ in range(2):
            self.client.post(reverse("login"), {"username": "admin@example.com", "password": "WrongPass123!"})

        response = self.client.post(
            reverse("login"),
            {"username": "admin@example.com", "password": "WrongPass123!"},
        )
        self.assertEqual(response.status_code, 423)
        self.assertIn("lockout_info", response.json())
        self.assertTrue(LoginLockout.objects.filter(identifier="admin@example.com", is_locked=True).exists())

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("login"),
            {"username": "admin@example.com", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "This account is inactive.")

    def test_logout_works(self):
        self.client.post(reverse("login"), {"username": "admin@example.com", "password": "StrongPass123!"})
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_protected_ajax_endpoint_returns_401_when_unauthenticated(self):
        response = self.client.get(reverse("auth-ping"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Authentication required.")

"""Dashboard view tests covering filters, summaries, and navigation state."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserType

from .test_support import DashboardFixtureMixin


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class DashboardViewTests(DashboardFixtureMixin, TestCase):
    """Exercise the production-facing dashboard views against real query patterns."""

    def test_dashboard_home_metrics_endpoint_respects_year_filter(self):
        """Home metrics JSON should follow the selected topbar filters."""

        response = self.client.get(reverse("dashboard:home-metrics"), {"year": "2026"})

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["enrolled"], 1)
        self.assertEqual(metrics["registered"], 1)
        self.assertEqual(metrics["pass_rate"], "100%")
        self.assertEqual(metrics["on_time_graduation"], 1)

    def test_programme_metrics_endpoint_respects_faculty_filter(self):
        """Programme metrics JSON should respect the selected faculty."""

        response = self.client.get(
            reverse("dashboard:programme-metrics"),
            {"faculty": self.science_faculty.name},
        )

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["programmes"], 1)
        self.assertEqual(metrics["registrations"], 1)
        self.assertEqual(metrics["students"], 1)
        self.assertEqual(metrics["average_pass_rate"], "100%")

    def test_insights_view_renders_live_operational_context(self):
        """Insights page should render real flagged-student and recommendation content."""

        response = self.client.get(reverse("dashboard:insights"))

        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(active_labels, ["Insights"])
        self.assertEqual(response.context["flagged_total"], 2)
        self.assertEqual(len(response.context["recommendations"]), 3)
        self.assertEqual(response.context["insight_summary_cards"][0]["label"], "At-Risk Students")
        self.assertNotIn("average below 50%", response.context["flagged_students"][0]["meta"].lower())

    def test_student_list_shows_each_student_once_with_latest_registration_details(self):
        """Students page should collapse multiple registrations into one latest row per student."""

        response = self.client.get(reverse("dashboard:students"))

        students = response.context["students"]
        alice_rows = [row for row in students if row["name"] == self.student_primary.full_name]
        self.assertEqual(len(alice_rows), 1)
        self.assertEqual(alice_rows[0]["program"], self.science_programme.name)
        self.assertEqual(alice_rows[0]["department"], self.science_department.name)
        self.assertEqual(alice_rows[0]["decision"], "Proceed")

    def test_programme_view_respects_faculty_filter(self):
        """Programme analytics should only include rows from the selected faculty."""

        response = self.client.get(
            reverse("dashboard:programme"),
            {"faculty": self.science_faculty.name},
        )

        programme_rows = response.context["programme_rows"]
        self.assertEqual(len(programme_rows), 1)
        self.assertEqual(programme_rows[0]["faculty"], self.science_faculty.name)
        self.assertEqual(programme_rows[0]["name"], self.science_programme.name)

    def test_sidebar_marks_current_section_active(self):
        """The current section should be the only active sidebar item."""

        response = self.client.get(reverse("dashboard:demographic"))

        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]
        self.assertEqual(active_labels, ["Demographics"])

    def test_admin_can_access_system_management(self):
        """Platform admins should see and access the system management workspace."""

        response = self.client.get(reverse("dashboard:system-management"))

        self.assertEqual(response.status_code, 200)
        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]
        self.assertEqual(active_labels, ["System Management"])

    def test_non_admin_cannot_access_system_management(self):
        """Non-admin users should be blocked from the system management page."""

        viewer_role = UserType.objects.create(code="viewer", name="Viewer")
        non_admin = get_user_model().objects.create_user(
            email="viewer@example.com",
            password="StrongPass123!",
            first_name="Viewer",
            last_name="User",
            user_type=viewer_role,
            is_active=True,
        )
        self.client.force_login(non_admin)

        response = self.client.get(reverse("dashboard:system-management"))

        self.assertEqual(response.status_code, 403)

    def test_system_management_can_create_user(self):
        """System management POST should provision a new user through the custom form."""

        response = self.client.post(
            reverse("dashboard:system-management"),
            {
                "action": "create-user",
                "first_name": "System",
                "last_name": "Operator",
                "email": "operator@example.com",
                "user_type": self.user_type.id,
                "is_active": "on",
                "grant_staff_access": "on",
                "password1": "OperatorPass123!",
                "password2": "OperatorPass123!",
                "next": reverse("dashboard:system-management"),
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = get_user_model().objects.get(email="operator@example.com")
        self.assertEqual(created_user.first_name, "System")
        self.assertTrue(created_user.is_active)
        self.assertTrue(created_user.is_staff)
        self.assertEqual(created_user.user_type, self.user_type)

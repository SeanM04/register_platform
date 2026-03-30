"""Dashboard view tests covering filters, summaries, and navigation state."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserType

from .models import AcademicPeriod, Course, CourseResult, Department, Faculty, Programme, Registration, Student
from .views import format_risk_monitor_drivers


class DashboardViewTests(TestCase):
    """Exercise the production-facing dashboard views against real query patterns."""

    def setUp(self):
        self.user_type, _ = UserType.objects.get_or_create(
            code="admin",
            defaults={"name": "Admin"},
        )
        self.user = get_user_model().objects.create_user(
            email="owner@example.com",
            password="StrongPass123!",
            first_name="Owner",
            last_name="User",
            user_type=self.user_type,
            is_active=True,
        )
        self.client.force_login(self.user)

        self.science_faculty = Faculty.objects.create(name="Science Faculty")
        self.commerce_faculty = Faculty.objects.create(name="Commerce Faculty")
        self.science_department = Department.objects.create(
            faculty=self.science_faculty,
            name="Department of Computing",
        )
        self.commerce_department = Department.objects.create(
            faculty=self.commerce_faculty,
            name="Department of Accounting",
        )
        self.science_programme = Programme.objects.create(
            department=self.science_department,
            external_id=101,
            code="BSC-INF",
            name="BSc Informatics",
        )
        self.commerce_programme = Programme.objects.create(
            department=self.commerce_department,
            external_id=102,
            code="BCOM-ACC",
            name="BCom Accounting",
        )
        self.period_2026 = AcademicPeriod.objects.create(
            external_id=202601,
            academic_year="1",
            semester="1",
            name="2026 Jan - June",
        )
        self.period_2025 = AcademicPeriod.objects.create(
            external_id=202501,
            academic_year="1",
            semester="2",
            name="2025 July - December",
        )
        self.course = Course.objects.create(code="CSC101", name="Foundations of Computing")

        self.student_primary = Student.objects.create(
            registration_number="REG001",
            first_names="Alice",
            surname="Ncube",
            gender="Female",
            place_of_birth="Bulawayo",
        )
        self.student_secondary = Student.objects.create(
            registration_number="REG002",
            first_names="Brian",
            surname="Moyo",
            gender="Male",
            place_of_birth="Harare",
        )

        self.primary_old_registration = Registration.objects.create(
            external_id=1,
            student=self.student_primary,
            programme=self.commerce_programme,
            period=self.period_2025,
            decision="pending",
            carrying=1,
        )
        self.primary_latest_registration = Registration.objects.create(
            external_id=2,
            student=self.student_primary,
            programme=self.science_programme,
            period=self.period_2026,
            decision="proceed",
            carrying=0,
        )
        self.secondary_registration = Registration.objects.create(
            external_id=3,
            student=self.student_secondary,
            programme=self.commerce_programme,
            period=self.period_2025,
            decision="retake",
            carrying=1,
        )

        CourseResult.objects.create(
            registration=self.primary_old_registration,
            course=self.course,
            mark=40,
        )
        CourseResult.objects.create(
            registration=self.primary_latest_registration,
            course=self.course,
            mark=78,
        )
        CourseResult.objects.create(
            registration=self.secondary_registration,
            course=self.course,
            mark=55,
        )

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

    def test_risk_view_lists_only_students_classified_as_at_risk(self):
        """Risk page should surface medium/high-risk students and exclude stable ones."""

        low_risk_student = Student.objects.create(
            registration_number="REG003",
            first_names="Chipo",
            surname="Sibanda",
            gender="Female",
            place_of_birth="Gweru",
        )
        low_risk_registration = Registration.objects.create(
            external_id=4,
            student=low_risk_student,
            programme=self.science_programme,
            period=self.period_2026,
            decision="proceed",
            carrying=0,
        )
        CourseResult.objects.create(
            registration=low_risk_registration,
            course=self.course,
            mark=76,
        )

        response = self.client.get(reverse("dashboard:risk"))

        risk_names = [row["name"] for row in response.context["risk_rows"]]
        risk_levels = {row["name"]: row["risk_level"] for row in response.context["risk_rows"]}
        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]

        self.assertIn(self.student_primary.full_name, risk_names)
        self.assertIn(self.student_secondary.full_name, risk_names)
        self.assertNotIn(low_risk_student.full_name, risk_names)
        self.assertEqual(risk_levels[self.student_primary.full_name], "Medium Risk")
        self.assertEqual(risk_levels[self.student_secondary.full_name], "High Risk")
        self.assertEqual(active_labels, ["Risk"])

    def test_risk_metrics_endpoint_returns_expected_counts(self):
        """Risk metrics JSON should summarise current medium/high-risk students."""

        response = self.client.get(reverse("dashboard:risk-metrics"))

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["at_risk_students"], 2)
        self.assertEqual(metrics["high_risk"], 1)
        self.assertEqual(metrics["medium_risk"], 1)
        self.assertEqual(metrics["multi_fail"], 0)

    def test_risk_view_hides_redundant_average_below_50_copy(self):
        """Risk rows should omit the repeated average-below-50 phrase from the table copy."""

        self.assertEqual(
            format_risk_monitor_drivers("average below 50%, 3+ failed modules, 1 carried module"),
            "3+ failed modules, 1 carried module",
        )
        self.assertEqual(
            format_risk_monitor_drivers("average below 50%"),
            "Performance needs support",
        )

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

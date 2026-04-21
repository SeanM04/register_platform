"""Dashboard view tests covering filters, summaries, and navigation state."""

import csv
import shutil
from pathlib import Path

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import UserType

from .models import (
    AcademicDecision,
    AttendanceType,
    Cohort,
    CompletionAnalysisRecord,
    Registration,
    Student,
    ZeroCompletionReason,
)
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
        """Insights page should render real flagged-student & recommendation content."""

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

    def test_student_list_search_preserves_matching_registration_context(self):
        """Students search should keep the latest registration inside the matched subset."""

        response = self.client.get(reverse("dashboard:students"), {"q": "Accounting"})

        students = response.context["students"]
        alice_rows = [row for row in students if row["name"] == self.student_primary.full_name]
        self.assertEqual(len(alice_rows), 1)
        self.assertEqual(alice_rows[0]["program"], self.commerce_programme.name)
        self.assertEqual(alice_rows[0]["department"], self.commerce_department.name)
        self.assertEqual(alice_rows[0]["decision"], "Pending")

    def test_student_list_paginates_in_the_database(self):
        """Students page should fetch only the requested page instead of materializing the full directory."""

        for index in range(3, 28):
            student = Student.objects.create(
                registration_number=f"REG{index:03d}",
                first_names=f"Student{index}",
                surname="LoadTest",
                gender="Female",
                place_of_birth="Windhoek",
            )
            Registration.objects.create(
                external_id=100 + index,
                student=student,
                programme=self.science_programme,
                period=self.period_2026,
                decision="proceed",
                carrying=0,
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("dashboard:students"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["students"]), 7)
        student_queries = [
            query["sql"]
            for query in queries.captured_queries
            if 'FROM "dashboard_student"' in query["sql"]
        ]
        self.assertTrue(student_queries)
        self.assertTrue(any("OFFSET 20" in query.upper() for query in student_queries))

    def test_programme_view_respects_faculty_filter(self):
        """Programme payload should only include rows from the selected faculty."""

        response = self.client.get(
            reverse("dashboard:programme-payload"),
            {"faculty": self.science_faculty.name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        programme_rows = response.json()["programme_rows"]
        self.assertEqual(len(programme_rows), 1)
        self.assertEqual(programme_rows[0]["faculty"], self.science_faculty.name)
        self.assertEqual(programme_rows[0]["name"], self.science_programme.name)

    def test_sidebar_marks_current_section_active(self):
        """The current section should be the only active sidebar item."""

        response = self.client.get(reverse("dashboard:demographic"))

        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]
        self.assertEqual(active_labels, ["Demographics"])

    def test_admin_can_access_system_management(self):
        """Platform admins should see & access the system management workspace."""

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


class RegistrarImportCommandTests(TestCase):
    """Verify the registrar import command decomposes CSVs into relational tables."""

    def _write_csv(self, directory, filename, headers, rows):
        path = Path(directory) / filename
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_import_command_loads_completion_export_and_calculates_age(self):
        temp_root = Path.cwd() / "data" / ".test_import_command"
        temp_dir = temp_root / "case_one"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        registrations_csv = self._write_csv(
            temp_dir,
            "Registrations.csv",
            [
                "id",
                "regnum",
                "firstnames",
                "surname",
                "programme_id",
                "programme_code",
                "programme_name",
                "faculty",
                "department",
                "dob",
                "gender",
                "place_of_birth",
                "psid",
                "attendance_type_id",
                "registration_id",
                "period_id",
                "academic_year",
                "semester",
                "period_name",
                "decision",
                "carrying",
            ],
            [
                {
                    "id": "1",
                    "regnum": "REG100",
                    "firstnames": "Ada",
                    "surname": "Moyo",
                    "programme_id": "10",
                    "programme_code": "BSC-STAT",
                    "programme_name": "Bachelor of Science in Statistics",
                    "faculty": "Science",
                    "department": "Mathematics",
                    "dob": "2000-01-10",
                    "gender": "Female",
                    "place_of_birth": "Harare",
                    "psid": "501",
                    "attendance_type_id": "1",
                    "registration_id": "9001",
                    "period_id": "202601",
                    "academic_year": "1",
                    "semester": "1",
                    "period_name": "2026 January - June",
                    "decision": "Pending",
                    "carrying": "0",
                }
            ],
        )
        marks_csv = self._write_csv(
            temp_dir,
            "course final marks by period.csv",
            [
                "code",
                "name",
                "period_name",
                "period_id",
                "regnum",
                "programme_code",
                "programme_name",
                "attendance_type",
                "mark",
                "gradingrule",
            ],
            [
                {
                    "code": "STA101",
                    "name": "Statistics I",
                    "period_name": "2026 January - June",
                    "period_id": "202601",
                    "regnum": "REG100",
                    "programme_code": "BSC-STAT",
                    "programme_name": "Bachelor of Science in Statistics",
                    "attendance_type": "Conventional",
                    "mark": "78",
                    "gradingrule": "100-50~P#49-0~F",
                }
            ],
        )
        completion_csv = self._write_csv(
            temp_dir,
            "completion_analysis.csv",
            [
                "Registration Number",
                "Student Name",
                "Programme",
                "Academic Stage",
                "Decision",
                "Effective Cohort",
                "Original Cohort",
                "Shifted",
                "Zero Completion Reason",
                "Completion Rate",
            ],
            [
                {
                    "Registration Number": "REG100",
                    "Student Name": "Ada Moyo",
                    "Programme": "Bachelor of Science in Statistics",
                    "Academic Stage": "Year 1, Semester 1",
                    "Decision": "Pending",
                    "Effective Cohort": "JANUARY 2026 - JUNE 2026",
                    "Original Cohort": "JANUARY 2026 - JUNE 2026",
                    "Shifted": "No",
                    "Zero Completion Reason": "",
                    "Completion Rate": "78%",
                }
            ],
        )

        call_command(
            "import_registrar_data",
            str(registrations_csv),
            str(marks_csv),
            str(completion_csv),
        )

        student = Student.objects.get(registration_number="REG100")
        registration = Registration.objects.get()
        self.assertEqual(student.age, student.current_age)
        self.assertEqual(registration.source_row_id, 1)
        self.assertEqual(registration.student_internal_id, 501)
        self.assertEqual(registration.attendance_type_record.name, "Conventional")
        self.assertEqual(registration.decision_record.label, "Pending")
        self.assertTrue(AttendanceType.objects.filter(name="Conventional").exists())
        self.assertTrue(AcademicDecision.objects.filter(label="Pending").exists())

        completion_row = CompletionAnalysisRecord.objects.get()
        self.assertEqual(completion_row.student.registration_number, "REG100")
        self.assertEqual(completion_row.programme.code, "BSC-STAT")
        self.assertEqual(completion_row.academic_year, "1")
        self.assertEqual(completion_row.semester, "1")
        self.assertEqual(str(completion_row.completion_rate), "78.00")
        self.assertFalse(completion_row.shifted)
        self.assertTrue(Cohort.objects.filter(name="JANUARY 2026 - JUNE 2026").exists())
        self.assertEqual(ZeroCompletionReason.objects.count(), 0)

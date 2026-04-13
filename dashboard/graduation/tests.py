"""Graduation analysis tests."""

from django.test import TestCase
from django.urls import reverse

from ..models import AcademicPeriod, Registration, Student
from ..test_support import DashboardFixtureMixin


class GraduationViewTests(DashboardFixtureMixin, TestCase):
    """Verify graduation analytics are served from dashboard models."""

    def setUp(self):
        super().setUp()
        self.period_2028 = AcademicPeriod.objects.create(
            external_id=202802,
            academic_year="4",
            semester="2",
            name="2028 July - December",
        )
        self.graduating_student = Student.objects.create(
            registration_number="REG003",
            first_names="Chipo",
            surname="Dube",
            gender="Female",
            place_of_birth="Gweru",
        )
        self.graduation_registration = Registration.objects.create(
            external_id=4,
            student=self.graduating_student,
            programme=self.science_programme,
            period=self.period_2028,
            decision="graduated",
            carrying=0,
        )

    def test_graduation_payload_uses_database_backed_analytics(self):
        response = self.client.get(
            reverse("dashboard:graduation-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["status"], "success")
        data = payload["data"]
        self.assertEqual(data["kpis"]["total_graduated_students"], 1)
        self.assertGreaterEqual(data["kpis"]["average_completion_graduation_rate"], 85.0)
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(data["students"][0]["regnum"], self.graduating_student.registration_number)
        self.assertEqual(data["students"][0]["graduation_stage"], "4.2")
        self.assertTrue(data["students"][0]["on_time"])
        self.assertTrue(data["charts"]["programme_graduation_rate"])
        self.assertTrue(data["charts"]["cohort_graduation_rate"])

    def test_graduation_filter_endpoints_return_database_options(self):
        programmes_response = self.client.get(reverse("dashboard:graduation-programmes"))
        faculties_response = self.client.get(reverse("dashboard:graduation-faculties"))

        self.assertEqual(programmes_response.status_code, 200)
        self.assertEqual(faculties_response.status_code, 200)

        programme_names = [row["programme_name"] for row in programmes_response.json()["programmes"]]
        faculty_names = [row["faculty"] for row in faculties_response.json()["faculties"]]

        self.assertIn(self.science_programme.name, programme_names)
        self.assertIn(self.commerce_programme.name, programme_names)
        self.assertIn(self.science_faculty.name, faculty_names)
        self.assertIn(self.commerce_faculty.name, faculty_names)

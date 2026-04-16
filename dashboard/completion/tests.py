"""Completion analysis tests."""

from django.test import TestCase
from django.urls import reverse

from ..test_support import DashboardFixtureMixin


class CompletionViewTests(DashboardFixtureMixin, TestCase):
    """Verify completion analytics are served from dashboard models."""

    def test_completion_payload_uses_database_backed_analytics(self):
        response = self.client.get(
            reverse("dashboard:completion-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["status"], "success")
        data = payload["data"]
        self.assertEqual(data["kpis"]["total_students"], 2)
        self.assertEqual(data["kpis"]["total_cohorts"], 2)
        self.assertEqual(data["kpis"]["gender_distribution"]["female"], 1)
        self.assertEqual(data["kpis"]["gender_distribution"]["male"], 1)
        self.assertEqual(len(data["students"]), 2)
        self.assertEqual(data["students"][0]["regnum"], self.student_primary.registration_number)
        self.assertTrue(data["charts"]["cohort_completion"])
        self.assertTrue(data["charts"]["programme_completion"])

    def test_completion_filter_endpoints_return_database_options(self):
        programmes_response = self.client.get(reverse("dashboard:completion-programmes"))
        faculties_response = self.client.get(reverse("dashboard:completion-faculties"))
        years_response = self.client.get(reverse("dashboard:completion-academic-years"))

        self.assertEqual(programmes_response.status_code, 200)
        self.assertEqual(faculties_response.status_code, 200)
        self.assertEqual(years_response.status_code, 200)

        programme_names = [row["programme_name"] for row in programmes_response.json()["programmes"]]
        faculty_names = [row["faculty"] for row in faculties_response.json()["faculties"]]
        academic_years = [row["year"] for row in years_response.json()["years"]]

        self.assertIn(self.science_programme.name, programme_names)
        self.assertIn(self.commerce_programme.name, programme_names)
        self.assertIn(self.science_faculty.name, faculty_names)
        self.assertIn(self.commerce_faculty.name, faculty_names)
        self.assertIn(self.period_2025.academic_year, academic_years)

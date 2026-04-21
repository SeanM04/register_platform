"""Completion analysis tests."""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings

from ..test_support import DashboardFixtureMixin
from ..models import AcademicPeriod, Course, CourseResult, Registration, Student
from services.completion_rules import get_zero_completion_decision, student_completion_percentage


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
        self.assertGreaterEqual(data["kpis"]["total_cohorts"], 1)
        self.assertIn("zero_completion_students", data["kpis"])
        self.assertIn("shifted_students", data["kpis"])
        self.assertEqual(data["kpis"]["gender_distribution"]["female"], 1)
        self.assertEqual(data["kpis"]["gender_distribution"]["male"], 1)
        self.assertEqual(len(data["students"]), 2)
        self.assertEqual(data["students"][0]["regnum"], self.student_primary.registration_number)
        self.assertTrue(data["charts"]["cohort_completion"])
        self.assertTrue(data["charts"]["programme_completion"])
        self.assertIn("zero_completion_drivers", data["charts"])
        self.assertIn("effective_cohort", data["students"][0])
        self.assertIn("original_cohort", data["students"][0])

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
        self.assertIn("2025", academic_years)

    @override_settings(
        AI_INSIGHTS_PROVIDER="rules",
        AI_INSIGHTS_ENABLED=False,
        OPENAI_INSIGHTS_ENABLED=False,
    )
    def test_completion_narratives_endpoint_supplies_rule_based_copy_by_default(self):
        response = self.client.get(
            reverse("dashboard:completion-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        narratives = payload["card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertIn("cohort", narratives["cards"])
        self.assertIn("programme", narratives["cards"])
        self.assertIn("drivers", narratives["cards"])
        self.assertTrue(narratives["cards"]["cohort"]["insight"])
        self.assertTrue(narratives["cards"]["programme"]["action"])
        self.assertIn(narratives["cards"]["drivers"]["severity"], {"stable", "medium", "high"})
        self.assertEqual(payload["diagnostics"]["status"], "rules")

    @override_settings(
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_INSIGHTS_MODEL="gpt-5-mini",
        OPENAI_INSIGHTS_TIMEOUT_SECONDS=10,
    )
    @patch("dashboard.completion.ai_insights._request_completion_openai_narratives")
    def test_completion_narratives_endpoint_can_use_openai_copy(self, mock_request):
        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"cohort\\":{\\"insight\\":\\"AI cohort insight\\",\\"action\\":\\"AI cohort action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"high\\"},\\"programme\\":{\\"insight\\":\\"AI programme insight\\",\\"action\\":\\"AI programme action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"drivers\\":{\\"insight\\":\\"AI drivers insight\\",\\"action\\":\\"AI drivers action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(
            reverse("dashboard:completion-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        narratives = payload["card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["cohort"]["insight"], "AI cohort insight")
        self.assertEqual(narratives["cards"]["programme"]["action"], "AI programme action")
        self.assertEqual(narratives["cards"]["drivers"]["severity"], "high")
        self.assertEqual(payload["diagnostics"]["status"], "ai")
        self.assertEqual(payload["diagnostics"]["returned_source"], "openai")

    def test_completion_payload_marks_shifted_students_after_zero_completion_decision(self):
        period_2026_second = AcademicPeriod.objects.create(
            external_id=202602,
            academic_year="1",
            semester="2",
            name="2026 July - December",
        )
        period_2027_first = AcademicPeriod.objects.create(
            external_id=202701,
            academic_year="2",
            semester="1",
            name="2027 Jan - June",
        )
        student = Student.objects.create(
            registration_number="REG004",
            first_names="Tariro",
            surname="Sibanda",
            gender="Female",
            place_of_birth="Mutare",
        )
        first_registration = Registration.objects.create(
            external_id=10,
            student=student,
            programme=self.science_programme,
            period=self.period_2026,
            decision="repeat",
            carrying=0,
        )
        second_registration = Registration.objects.create(
            external_id=11,
            student=student,
            programme=self.science_programme,
            period=period_2027_first,
            decision="proceed",
            carrying=0,
        )
        CourseResult.objects.create(registration=first_registration, course=self.course, mark=82)
        CourseResult.objects.create(registration=second_registration, course=self.course, mark=74)

        response = self.client.get(
            reverse("dashboard:completion-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        data = response.json()["data"]
        shifted_student = next(row for row in data["students"] if row["regnum"] == student.registration_number)
        zero_driver_labels = [row["label"] for row in data["charts"]["zero_completion_drivers"]]

        self.assertTrue(shifted_student["is_shifted"])
        self.assertNotEqual(shifted_student["effective_cohort"], shifted_student["original_cohort"])
        self.assertIn("Repeat shift", zero_driver_labels)

    def test_completion_payload_sets_zero_completion_for_four_failed_courses(self):
        period_2027_second = AcademicPeriod.objects.create(
            external_id=202702,
            academic_year="1",
            semester="2",
            name="2027 July - December",
        )
        student = Student.objects.create(
            registration_number="REG005",
            first_names="Nomsa",
            surname="Mpofu",
            gender="Female",
            place_of_birth="Masvingo",
        )
        registration = Registration.objects.create(
            external_id=12,
            student=student,
            programme=self.commerce_programme,
            period=period_2027_second,
            decision="proceed",
            carrying=0,
        )
        extra_courses = [
            Course.objects.create(code="ACC201", name="Accounting 1"),
            Course.objects.create(code="ACC202", name="Accounting 2"),
            Course.objects.create(code="ACC203", name="Accounting 3"),
            Course.objects.create(code="ACC204", name="Accounting 4"),
        ]
        for course, mark in zip(extra_courses, [40, 42, 35, 48]):
            CourseResult.objects.create(registration=registration, course=course, mark=mark)

        response = self.client.get(
            reverse("dashboard:completion-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        data = response.json()["data"]
        zero_student = next(row for row in data["students"] if row["regnum"] == student.registration_number)
        self.assertEqual(zero_student["completion_rate"], 0.0)
        self.assertEqual(zero_student["zero_completion_reason"], "Failed 4+ courses")


class CompletionRuleTests(TestCase):
    """Verify the documented completion rule helpers."""

    def test_special_decision_forces_zero_completion_and_shift(self):
        decision = get_zero_completion_decision("Repeat level")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.shift_semesters, 1)
        self.assertEqual(student_completion_percentage([92, 88], decision="repeat level"), 0.0)

    def test_four_failed_courses_force_zero_completion(self):
        self.assertEqual(
            student_completion_percentage([65, 40, 32, 44, 21]),
            0.0,
        )

    def test_completion_uses_passed_course_ratio_when_failures_are_three_or_less(self):
        self.assertEqual(
            student_completion_percentage([72, 68, 49, 88]),
            75.0,
        )

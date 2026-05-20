"""Graduation analysis tests."""

from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from ..models import AcademicPeriod, Programme, Registration, Student
from ..test_support import DashboardFixtureMixin


class GraduationViewTests(DashboardFixtureMixin, TestCase):
    """Verify graduation analytics and narratives are served from dashboard models."""

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
        Registration.objects.create(
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
        self.assertIn("average_graduation_rate", data["kpis"])
        self.assertIn("on_time_graduation_rate", data["kpis"])
        self.assertIn("best_faculty_rate", data["kpis"])
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(data["students"][0]["regnum"], self.graduating_student.registration_number)
        self.assertEqual(data["students"][0]["detail_slug"], self.graduating_student.registration_number.lower())
        self.assertEqual(data["students"][0]["graduation_stage"], "4.2")
        self.assertTrue(data["students"][0]["on_time"])
        self.assertTrue(data["charts"]["programme_graduation_rate"])
        self.assertTrue(data["charts"]["cohort_graduation_rate"])
        self.assertTrue(data["charts"]["faculty_graduation_rate"])
        self.assertTrue(data["charts"]["graduation_timing"])

    def test_graduation_payload_sorts_students_by_surname(self):
        second_graduate = Student.objects.create(
            registration_number="REG004",
            first_names="Alice",
            surname="Anderson",
            gender="Female",
            place_of_birth="Harare",
        )
        Registration.objects.create(
            external_id=5,
            student=second_graduate,
            programme=self.science_programme,
            period=self.period_2028,
            decision="graduated",
            carrying=0,
        )

        response = self.client.get(
            reverse("dashboard:graduation-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        regnums = [row["regnum"] for row in response.json()["data"]["students"]]
        self.assertEqual(regnums, [second_graduate.registration_number, self.graduating_student.registration_number])

    def test_graduation_drilldown_returns_filtered_student_rows(self):
        response = self.client.get(
            reverse("dashboard:graduation-drilldown"),
            {
                "chart_key": "graduation_programmes",
                "bucket_key": self.science_programme.name,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["rows"][0]["name"], self.graduating_student.full_name)
        self.assertEqual(payload["pagination"]["current_page"], 1)
        self.assertEqual(payload["rows"][0]["programme"], self.science_programme.name)

    def test_graduation_drilldown_supports_next_and_previous_pages(self):
        second_student = Student.objects.create(
            registration_number="REG098",
            first_names="Second",
            surname="Graduate",
            gender="Female",
            place_of_birth="Mutare",
        )
        Registration.objects.create(
            external_id=98,
            student=second_student,
            programme=self.science_programme,
            period=self.period_2028,
            decision="graduated",
            carrying=0,
        )

        first_page = self.client.get(
            reverse("dashboard:graduation-drilldown"),
            {
                "chart_key": "graduation_programmes",
                "bucket_key": self.science_programme.name,
                "page": 1,
                "page_size": 1,
            },
        ).json()["data"]
        second_page = self.client.get(
            reverse("dashboard:graduation-drilldown"),
            {
                "chart_key": "graduation_programmes",
                "bucket_key": self.science_programme.name,
                "page": 2,
                "page_size": 1,
            },
        ).json()["data"]

        self.assertEqual(first_page["pagination"]["total_pages"], 2)
        self.assertTrue(first_page["pagination"]["has_next"])
        self.assertFalse(first_page["pagination"]["has_previous"])
        self.assertFalse(second_page["pagination"]["has_next"])
        self.assertTrue(second_page["pagination"]["has_previous"])
        self.assertNotEqual(first_page["rows"][0]["name"], second_page["rows"][0]["name"])

    def test_graduation_readiness_drilldown_returns_one_step_students(self):
        readiness_student = Student.objects.create(
            registration_number="REG199",
            first_names="Ready",
            surname="Student",
            gender="Female",
            place_of_birth="Mutare",
        )
        year1_sem1 = AcademicPeriod.objects.create(
            external_id=204001,
            academic_year="1",
            semester="1",
            name="2040 January - June",
        )
        year1_sem2 = AcademicPeriod.objects.create(
            external_id=204002,
            academic_year="1",
            semester="2",
            name="2040 July - December",
        )
        year2_sem1 = AcademicPeriod.objects.create(
            external_id=204101,
            academic_year="2",
            semester="1",
            name="2041 January - June",
        )
        year2_sem2 = AcademicPeriod.objects.create(
            external_id=204102,
            academic_year="2",
            semester="2",
            name="2041 July - December",
        )
        year3_sem1 = AcademicPeriod.objects.create(
            external_id=204201,
            academic_year="3",
            semester="1",
            name="2042 January - June",
        )
        year3_sem2 = AcademicPeriod.objects.create(
            external_id=204202,
            academic_year="3",
            semester="2",
            name="2042 July - December",
        )
        year4_sem1 = AcademicPeriod.objects.create(
            external_id=204301,
            academic_year="4",
            semester="1",
            name="2043 January - June",
        )
        for external_id, period in [
            (40, year1_sem1),
            (41, year1_sem2),
            (42, year2_sem1),
            (43, year2_sem2),
            (44, year3_sem1),
            (45, year3_sem2),
            (46, year4_sem1),
        ]:
            Registration.objects.create(
                external_id=external_id,
                student=readiness_student,
                programme=self.science_programme,
                period=period,
                decision="Proceed",
                carrying=0,
            )

        response = self.client.get(
            reverse("dashboard:graduation-drilldown"),
            {
                "chart_key": "readiness_programmes",
                "bucket_key": self.science_programme.name,
            },
        )

        payload = response.json()["data"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["rows"][0]["name"], readiness_student.full_name)
        self.assertEqual(payload["rows"][0]["status"], "One step away")

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

    def test_late_starting_masters_records_do_not_count_as_graduated_without_relative_target_completion(self):
        masters_programme = Programme.objects.create(
            department=self.commerce_department,
            external_id=103,
            code="MSC-TOUR",
            name="Masters of Science in Tourism and Hospitality Management",
        )
        masters_student = Student.objects.create(
            registration_number="REG004",
            first_names="Lindiwe",
            surname="Mlambo",
            gender="Female",
            place_of_birth="Masvingo",
        )
        year3_sem1 = AcademicPeriod.objects.create(
            external_id=202701,
            academic_year="3",
            semester="1",
            name="2027 January - June",
        )
        year3_sem2 = AcademicPeriod.objects.create(
            external_id=202702,
            academic_year="3",
            semester="2",
            name="2027 July - December",
        )
        year4_sem1 = AcademicPeriod.objects.create(
            external_id=202801,
            academic_year="4",
            semester="1",
            name="2028 January - June",
        )
        Registration.objects.create(
            external_id=10,
            student=masters_student,
            programme=masters_programme,
            period=year3_sem1,
            decision="pending",
            carrying=0,
        )
        Registration.objects.create(
            external_id=11,
            student=masters_student,
            programme=masters_programme,
            period=year3_sem2,
            decision="proceed",
            carrying=0,
        )
        Registration.objects.create(
            external_id=12,
            student=masters_student,
            programme=masters_programme,
            period=year4_sem1,
            decision="proceed",
            carrying=0,
        )

        response = self.client.get(
            reverse("dashboard:graduation-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        data = response.json()["data"]
        graduate_regnums = {row["regnum"] for row in data["students"]}
        self.assertNotIn(masters_student.registration_number, graduate_regnums)

    def test_jumped_academic_year_labels_do_not_create_phantom_masters_graduates(self):
        masters_programme = Programme.objects.create(
            department=self.commerce_department,
            external_id=104,
            code="MSC-HOSP",
            name="Masters of Science in Hospitality Analytics",
        )
        masters_student = Student.objects.create(
            registration_number="REG005",
            first_names="Tariro",
            surname="Sibanda",
            gender="Female",
            place_of_birth="Mutare",
        )
        first_visible_period = AcademicPeriod.objects.create(
            external_id=202412,
            academic_year="1",
            semester="2",
            name="2024 July - December",
        )
        second_visible_period = AcademicPeriod.objects.create(
            external_id=202507,
            academic_year="3",
            semester="2",
            name="2025 March - July",
        )
        third_visible_period = AcademicPeriod.objects.create(
            external_id=202512,
            academic_year="3",
            semester="1",
            name="2025 August - December",
        )
        Registration.objects.create(
            external_id=20,
            student=masters_student,
            programme=masters_programme,
            period=first_visible_period,
            decision="pending",
            carrying=0,
        )
        Registration.objects.create(
            external_id=21,
            student=masters_student,
            programme=masters_programme,
            period=second_visible_period,
            decision="proceed",
            carrying=0,
        )
        Registration.objects.create(
            external_id=22,
            student=masters_student,
            programme=masters_programme,
            period=third_visible_period,
            decision="proceed",
            carrying=0,
        )

        response = self.client.get(
            reverse("dashboard:graduation-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        data = response.json()["data"]
        graduate_regnums = {row["regnum"] for row in data["students"]}
        self.assertNotIn(masters_student.registration_number, graduate_regnums)
        self.assertTrue(
            any(
                row["programme_id"] == masters_programme.external_id and row["student_count"] >= 1
                for row in data["charts"]["readiness_programmes"]
            )
        )

    def test_target_stage_with_proceed_decision_counts_as_graduated(self):
        target_stage_student = Student.objects.create(
            registration_number="REG006",
            first_names="Nyasha",
            surname="Moyo",
            gender="Male",
            place_of_birth="Harare",
        )
        year1_sem1 = AcademicPeriod.objects.create(
            external_id=203501,
            academic_year="1",
            semester="1",
            name="2025 January - June",
        )
        year1_sem2 = AcademicPeriod.objects.create(
            external_id=203502,
            academic_year="1",
            semester="2",
            name="2025 July - December",
        )
        year2_sem1 = AcademicPeriod.objects.create(
            external_id=203601,
            academic_year="2",
            semester="1",
            name="2026 January - June",
        )
        year2_sem2 = AcademicPeriod.objects.create(
            external_id=203602,
            academic_year="2",
            semester="2",
            name="2026 July - December",
        )
        year3_sem1 = AcademicPeriod.objects.create(
            external_id=203701,
            academic_year="3",
            semester="1",
            name="2027 January - June",
        )
        year3_sem2 = AcademicPeriod.objects.create(
            external_id=203702,
            academic_year="3",
            semester="2",
            name="2027 July - December",
        )
        year4_sem1 = AcademicPeriod.objects.create(
            external_id=203801,
            academic_year="4",
            semester="1",
            name="2028 January - June",
        )
        for external_id, period, decision in [
            (23, year1_sem1, "Proceed"),
            (24, year1_sem2, "Proceed"),
            (25, year2_sem1, "Proceed"),
            (26, year2_sem2, "Proceed"),
            (27, year3_sem1, "Proceed"),
            (28, year3_sem2, "Proceed"),
            (29, year4_sem1, "Proceed"),
        ]:
            Registration.objects.create(
                external_id=external_id,
                student=target_stage_student,
                programme=self.commerce_programme,
                period=period,
                decision=decision,
                carrying=0,
            )
        Registration.objects.create(
            external_id=30,
            student=target_stage_student,
            programme=self.commerce_programme,
            period=self.period_2028,
            decision="Proceed",
            carrying=0,
        )

        response = self.client.get(
            reverse("dashboard:graduation-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        data = response.json()["data"]
        graduate_regnums = {row["regnum"] for row in data["students"]}

        self.assertIn(target_stage_student.registration_number, graduate_regnums)

    @override_settings(
        AI_INSIGHTS_PROVIDER="rules",
        AI_INSIGHTS_ENABLED=False,
        OPENAI_INSIGHTS_ENABLED=False,
    )
    def test_graduation_narratives_endpoint_supplies_rule_based_copy_by_default(self):
        response = self.client.get(
            reverse("dashboard:graduation-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        narratives = payload["card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertIn("programme", narratives["cards"])
        self.assertIn("cohort", narratives["cards"])
        self.assertIn("faculty", narratives["cards"])
        self.assertIn("timing", narratives["cards"])
        self.assertTrue(narratives["cards"]["programme"]["insight"])
        self.assertTrue(narratives["cards"]["timing"]["action"])
        self.assertIn(narratives["cards"]["faculty"]["severity"], {"stable", "medium", "high"})
        self.assertEqual(payload["diagnostics"]["status"], "rules")

    @override_settings(
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
        OPENAI_INSIGHTS_MODEL="gpt-5-mini",
        OPENAI_INSIGHTS_TIMEOUT_SECONDS=10,
    )
    @patch("dashboard.graduation.ai_insights._request_graduation_openai_narratives")
    def test_graduation_narratives_endpoint_can_use_openai_copy(self, mock_request):
        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"programme\\":{\\"insight\\":\\"AI programme insight\\",\\"action\\":\\"AI programme action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"high\\"},\\"cohort\\":{\\"insight\\":\\"AI cohort insight\\",\\"action\\":\\"AI cohort action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"},\\"faculty\\":{\\"insight\\":\\"AI faculty insight\\",\\"action\\":\\"AI faculty action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"timing\\":{\\"insight\\":\\"AI timing insight\\",\\"action\\":\\"AI timing action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(
            reverse("dashboard:graduation-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        narratives = payload["card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["programme"]["insight"], "AI programme insight")
        self.assertEqual(narratives["cards"]["cohort"]["action"], "AI cohort action")
        self.assertEqual(narratives["cards"]["timing"]["severity"], "medium")
        self.assertEqual(payload["diagnostics"]["status"], "ai")
        self.assertEqual(payload["diagnostics"]["returned_source"], "openai")


class GraduationReadinessTests(DashboardFixtureMixin, TestCase):
    """Verify readiness metadata when the snapshot has progression but no graduates."""

    def test_graduation_payload_exposes_readiness_when_no_visible_graduates_exist(self):
        response = self.client.get(
            reverse("dashboard:graduation-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        data = payload["data"]

        self.assertEqual(data["kpis"]["total_graduated_students"], 0)
        self.assertFalse(data["meta"]["has_graduates"])
        self.assertTrue(data["meta"]["snapshot_message"])
        self.assertIn("students_one_step_from_target", data["meta"])
        self.assertIn("students_within_two_steps", data["meta"])
        self.assertIn("readiness_programmes", data["charts"])
        self.assertIn("readiness_cohorts", data["charts"])

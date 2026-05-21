"""Risk feature tests."""

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import AcademicPeriod, CourseResult, Registration, Student
from ..test_support import DashboardFixtureMixin
from .services import (
    assess_student_risk,
    build_student_risk_profiles_from_registrations,
    format_risk_monitor_drivers,
)


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class RiskViewTests(DashboardFixtureMixin, TestCase):
    """Exercise risk analytics against the shared dashboard fixture."""

    def _add_low_risk_student(self, regnum="REG003", external_id=4):
        low_risk_student = Student.objects.create(
            registration_number=regnum,
            first_names=f"Chipo{regnum[-1]}",
            surname=f"Sibanda{regnum[-1]}",
            gender="Female",
            place_of_birth="Gweru",
        )
        low_risk_registration = Registration.objects.create(
            external_id=external_id,
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
        return low_risk_student

    def test_risk_view_renders_lightweight_shell(self):
        """Risk view should return a shell and defer the heavy payload."""

        response = self.client.get(reverse("dashboard:risk"))

        self.assertEqual(response.context["summary_cards"][0]["value"], "--")
        self.assertNotIn("risk_rows", response.context)
        self.assertContains(response, reverse("dashboard:risk-payload"))

    def test_risk_payload_lists_only_students_classified_as_at_risk(self):
        """Risk payload should surface medium/high-risk students and exclude stable ones."""

        low_risk_student = self._add_low_risk_student()

        shell_response = self.client.get(reverse("dashboard:risk"))
        response = self.client.get(reverse("dashboard:risk-payload"))
        payload = response.json()

        risk_names = [row["name"] for row in payload["register"]["rows"]]
        risk_levels = {row["name"]: row["risk_level"] for row in payload["register"]["rows"]}
        active_labels = [item["label"] for item in shell_response.context["sidebar_items"] if item["is_active"]]

        self.assertIn(self.student_primary.full_name, risk_names)
        self.assertIn(self.student_secondary.full_name, risk_names)
        self.assertNotIn(low_risk_student.full_name, risk_names)
        self.assertEqual(risk_levels[self.student_primary.full_name], "Medium Risk")
        self.assertEqual(risk_levels[self.student_secondary.full_name], "High Risk")
        self.assertEqual(active_labels, ["Risk"])

    def test_risk_payload_orders_rows_by_surname(self):
        self._add_low_risk_student(regnum="REG013", external_id=13)

        response = self.client.get(reverse("dashboard:risk-payload"))
        rows = response.json()["register"]["rows"]
        names = [row["name"] for row in rows]

        self.assertEqual(
            names,
            sorted(
                names,
                key=lambda value: (value.split()[-1].lower(), " ".join(value.split()[:-1]).lower()),
            ),
        )

    def test_risk_payload_action_register_uses_ten_rows_per_page(self):
        for index in range(3, 14):
            self._add_low_risk_student(regnum=f"REG0{index}", external_id=index + 1)

        payload = self.client.get(reverse("dashboard:risk-payload")).json()
        register = payload["register"]

        self.assertEqual(register["page_size"], 10)
        self.assertEqual(len(register["rows"]), 10)
        self.assertTrue(register["has_next"])

    def test_risk_payload_supplies_story_chart_rows(self):
        """Risk payload should expose the distribution, driver, level, and programme chart payloads."""

        response = self.client.get(reverse("dashboard:risk-payload"))
        payload = response.json()

        distribution_rows = payload["risk_distribution_rows"]
        driver_rows = payload["risk_driver_rows"]
        level_rows = payload["risk_level_rows"]
        programme_rows = payload["risk_programme_rows"]

        self.assertEqual(distribution_rows[0]["key"], "low")
        self.assertEqual(distribution_rows[1]["key"], "moderate")
        self.assertEqual(distribution_rows[1]["count"], 1)
        self.assertEqual(distribution_rows[2]["key"], "high")
        self.assertEqual(distribution_rows[2]["count"], 1)
        self.assertEqual(driver_rows[0]["label"], "1 carried module")
        self.assertEqual(driver_rows[0]["count"], 3)
        self.assertEqual(level_rows[0]["level"], "Year 1 Semester 1")
        self.assertEqual(level_rows[0]["high_risk"], 1)
        self.assertEqual(level_rows[0]["medium_risk"], 1)
        self.assertEqual(programme_rows[0]["programme"], self.commerce_programme.name)
        self.assertEqual(programme_rows[0]["high_risk"], 1)

    def test_risk_payload_rebases_imported_levels_like_student_detail(self):
        student = Student.objects.create(
            registration_number="REG777",
            first_names="Level",
            surname="Shift",
            gender="Female",
            place_of_birth="Mutare",
        )
        year_two_period = AcademicPeriod.objects.create(
            external_id=202701,
            academic_year="2",
            semester="1",
            name="2027 January - June",
        )
        raw_year_two = Registration.objects.create(
            external_id=777,
            student=student,
            programme=self.science_programme,
            period=year_two_period,
            decision="repeat",
            carrying=1,
        )
        CourseResult.objects.create(
            registration=raw_year_two,
            course=self.course,
            mark=42,
        )

        risk_row = build_student_risk_profiles_from_registrations([raw_year_two])[0]

        self.assertEqual(risk_row["academic_level"], "Year 1 Semester 1")

    def test_risk_profiles_fall_back_to_historical_average_when_visible_registration_has_no_marks(self):
        older_period = AcademicPeriod.objects.create(
            external_id=202401,
            academic_year="1",
            semester="1",
            name="2024 January - June",
        )
        latest_period = AcademicPeriod.objects.create(
            external_id=202402,
            academic_year="1",
            semester="2",
            name="2024 July - December",
        )
        student = Student.objects.create(
            registration_number="REG778",
            first_names="Average",
            surname="Fallback",
            gender="Female",
            place_of_birth="Mutare",
        )
        older_registration = Registration.objects.create(
            external_id=778,
            student=student,
            programme=self.science_programme,
            period=older_period,
            decision="proceed",
            carrying=0,
        )
        latest_registration = Registration.objects.create(
            external_id=779,
            student=student,
            programme=self.science_programme,
            period=latest_period,
            decision="retake",
            carrying=1,
        )
        CourseResult.objects.create(
            registration=older_registration,
            course=self.course,
            mark=66,
        )

        response = self.client.get(
            reverse("dashboard:risk-payload"),
            {"year": "2024", "period": "July - December"},
        )
        payload = response.json()
        row = next(item for item in payload["register"]["rows"] if item["name"] == student.full_name)

        self.assertEqual(row["average_mark"], 66)

    def test_risk_metrics_endpoint_returns_expected_counts(self):
        """Risk metrics JSON should summarise current medium/high-risk students."""

        response = self.client.get(reverse("dashboard:risk-metrics"))

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["at_risk_students"], 2)
        self.assertEqual(metrics["high_risk"], 1)
        self.assertEqual(metrics["medium_risk"], 1)
        self.assertEqual(metrics["multi_fail"], 0)

    def test_risk_drilldown_payload_returns_modal_rows_for_distribution_selection(self):
        """Risk chart drill-down should return modal-ready rows instead of requiring page navigation."""

        low_risk_student = self._add_low_risk_student()

        response = self.client.get(
            reverse("dashboard:risk-drilldown"),
            {"chart": "distribution", "bucket": "low"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()
        row_names = [row["name"] for row in payload["rows"]]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["title"], "Low Risk (0-1) Students")
        self.assertIn(low_risk_student.full_name, row_names)
        self.assertTrue(all("detail_url" in row for row in payload["rows"]))

    def test_risk_drilldown_payload_supports_next_and_previous_pages(self):
        self._add_low_risk_student("REG003", 4)
        self._add_low_risk_student("REG004", 5)

        first_page = self.client.get(
            reverse("dashboard:risk-drilldown"),
            {"chart": "distribution", "bucket": "low", "page": 1, "page_size": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        ).json()
        second_page = self.client.get(
            reverse("dashboard:risk-drilldown"),
            {"chart": "distribution", "bucket": "low", "page": 2, "page_size": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        ).json()

        self.assertEqual(first_page["page_count"], 2)
        self.assertEqual(first_page["page"], 1)
        self.assertEqual(second_page["page"], 2)
        self.assertNotEqual(first_page["rows"][0]["name"], second_page["rows"][0]["name"])

    def test_risk_driver_copy_hides_redundant_average_below_50_text(self):
        """Risk rows should omit the repeated average-below-50 phrase from the table copy."""

        self.assertEqual(
            format_risk_monitor_drivers("average below 50%, 3+ failed modules, 1 carried module"),
            "3+ failed modules, 1 carried module",
        )
        self.assertEqual(
            format_risk_monitor_drivers("average below 50%"),
            "Performance needs support",
        )

    def test_single_failed_module_is_grouped_under_one_carried_module(self):
        failed_only_student = Student.objects.create(
            registration_number="REG301",
            first_names="Tafadzwa",
            surname="Moyo",
            gender="Female",
            place_of_birth="Harare",
        )
        failed_only_registration = Registration.objects.create(
            external_id=301,
            student=failed_only_student,
            programme=self.science_programme,
            period=self.period_2026,
            decision="proceed",
            carrying=0,
        )
        CourseResult.objects.create(
            registration=failed_only_registration,
            course=self.course,
            mark=45,
        )

        carrying_only_student = Student.objects.create(
            registration_number="REG302",
            first_names="Tanaka",
            surname="Dube",
            gender="Male",
            place_of_birth="Mutare",
        )
        carrying_only_registration = Registration.objects.create(
            external_id=302,
            student=carrying_only_student,
            programme=self.science_programme,
            period=self.period_2026,
            decision="proceed",
            carrying=1,
        )
        CourseResult.objects.create(
            registration=carrying_only_registration,
            course=self.course,
            mark=72,
        )

        failed_assessment = assess_student_risk([failed_only_registration])
        carrying_assessment = assess_student_risk([carrying_only_registration])

        self.assertIn("carrying_1", failed_assessment["risk_driver_tags"])
        self.assertNotIn("failed_1", failed_assessment["risk_driver_tags"])
        self.assertIn("1 carried module", failed_assessment["risk_drivers"])
        self.assertEqual(carrying_assessment["risk_driver_tags"], ["carrying_1"])

    def test_risk_payload_supplies_rule_based_card_narratives_by_default(self):
        """Risk payload should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:risk-payload"))
        payload = response.json()

        narratives = payload["risk_card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertIn("distribution", narratives["cards"])
        self.assertIn("drivers", narratives["cards"])
        self.assertIn("levels", narratives["cards"])
        self.assertIn("programmes", narratives["cards"])
        self.assertTrue(narratives["cards"]["distribution"]["insight"])
        self.assertTrue(narratives["cards"]["drivers"]["action"])
        self.assertEqual(narratives["cards"]["distribution"]["severity"], "medium")
        self.assertEqual(narratives["cards"]["drivers"]["confidence"], "low")

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.risk.ai_insights._request_risk_openai_narratives")
    def test_risk_payload_uses_ai_card_narratives_when_available(self, mock_request):
        """Risk payload should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"distribution\\":{\\"insight\\":\\"AI distribution insight\\",\\"action\\":\\"AI distribution action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"},\\"drivers\\":{\\"insight\\":\\"AI driver insight\\",\\"action\\":\\"AI driver action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"levels\\":{\\"insight\\":\\"AI level insight\\",\\"action\\":\\"AI level action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"programmes\\":{\\"insight\\":\\"AI programme insight\\",\\"action\\":\\"AI programme action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:risk-payload"))
        payload = response.json()

        narratives = payload["risk_card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["distribution"]["insight"], "AI distribution insight")
        self.assertEqual(narratives["cards"]["drivers"]["action"], "AI driver action")
        self.assertEqual(narratives["cards"]["levels"]["insight"], "AI level insight")
        self.assertEqual(narratives["cards"]["programmes"]["action"], "AI programme action")
        self.assertEqual(narratives["cards"]["distribution"]["severity"], "high")
        self.assertEqual(narratives["cards"]["programmes"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.risk.ai_insights._request_risk_google_narratives")
    def test_risk_payload_can_use_google_card_narratives(self, mock_request):
        """Risk payload should support Gemini-generated narratives."""

        mock_request.return_value = """
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "{\\"cards\\":{\\"distribution\\":{\\"insight\\":\\"Gemini distribution insight\\",\\"action\\":\\"Gemini distribution action\\"},\\"drivers\\":{\\"insight\\":\\"Gemini drivers insight\\",\\"action\\":\\"Gemini drivers action\\"},\\"levels\\":{\\"insight\\":\\"Gemini levels insight\\",\\"action\\":\\"Gemini levels action\\"},\\"programmes\\":{\\"insight\\":\\"Gemini programmes insight\\",\\"action\\":\\"Gemini programmes action\\"}}}"
                            }
                        ]
                    }
                }
            ]
        }
        """

        response = self.client.get(reverse("dashboard:risk-payload"))
        payload = response.json()

        narratives = payload["risk_card_narratives"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(narratives["cards"]["distribution"]["insight"], "Gemini distribution insight")
        self.assertEqual(narratives["cards"]["drivers"]["action"], "Gemini drivers action")
        self.assertEqual(narratives["cards"]["levels"]["insight"], "Gemini levels insight")
        self.assertEqual(narratives["cards"]["programmes"]["action"], "Gemini programmes action")
        self.assertEqual(narratives["cards"]["drivers"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["drivers"]["confidence"], "low")

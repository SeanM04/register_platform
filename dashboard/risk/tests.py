"""Risk feature tests."""

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import CourseResult, Registration, Student
from ..test_support import DashboardFixtureMixin
from .services import format_risk_monitor_drivers


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class RiskViewTests(DashboardFixtureMixin, TestCase):
    """Exercise risk analytics against the shared dashboard fixture."""

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

    def test_risk_view_supplies_story_chart_rows(self):
        """Risk page should expose the distribution, driver, level, and programme chart payloads."""

        response = self.client.get(reverse("dashboard:risk"))

        distribution_rows = response.context["risk_distribution_rows"]
        driver_rows = response.context["risk_driver_rows"]
        level_rows = response.context["risk_level_rows"]
        programme_rows = response.context["risk_programme_rows"]

        self.assertEqual(distribution_rows[0]["key"], "critical")
        self.assertEqual(distribution_rows[1]["key"], "high")
        self.assertEqual(distribution_rows[1]["count"], 1)
        self.assertEqual(distribution_rows[2]["key"], "moderate")
        self.assertEqual(distribution_rows[2]["count"], 1)
        self.assertEqual(driver_rows[0]["label"], "Average 50-59%")
        self.assertEqual(driver_rows[0]["count"], 2)
        self.assertEqual(level_rows[0]["level"], "Year 1, Semester 2")
        self.assertEqual(level_rows[0]["high_risk"], 1)
        self.assertEqual(programme_rows[0]["programme"], self.commerce_programme.name)
        self.assertEqual(programme_rows[0]["high_risk"], 1)

    def test_risk_metrics_endpoint_returns_expected_counts(self):
        """Risk metrics JSON should summarise current medium/high-risk students."""

        response = self.client.get(reverse("dashboard:risk-metrics"))

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["at_risk_students"], 2)
        self.assertEqual(metrics["high_risk"], 1)
        self.assertEqual(metrics["medium_risk"], 1)
        self.assertEqual(metrics["multi_fail"], 0)

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

    def test_risk_view_supplies_rule_based_card_narratives_by_default(self):
        """Risk overview cards should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:risk"))

        narratives = response.context["risk_card_narratives"]

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
    def test_risk_view_uses_ai_card_narratives_when_available(self, mock_request):
        """Risk overview cards should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"distribution\\":{\\"insight\\":\\"AI distribution insight\\",\\"action\\":\\"AI distribution action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"},\\"drivers\\":{\\"insight\\":\\"AI driver insight\\",\\"action\\":\\"AI driver action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"levels\\":{\\"insight\\":\\"AI level insight\\",\\"action\\":\\"AI level action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"programmes\\":{\\"insight\\":\\"AI programme insight\\",\\"action\\":\\"AI programme action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:risk"))

        narratives = response.context["risk_card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["distribution"]["insight"], "AI distribution insight")
        self.assertEqual(narratives["cards"]["drivers"]["action"], "AI driver action")
        self.assertEqual(narratives["cards"]["levels"]["insight"], "AI level insight")
        self.assertEqual(narratives["cards"]["programmes"]["action"], "AI programme action")
        self.assertEqual(narratives["cards"]["distribution"]["severity"], "high")
        self.assertEqual(narratives["cards"]["programmes"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.risk.ai_insights._request_risk_google_narratives")
    def test_risk_view_can_use_google_card_narratives(self, mock_request):
        """Risk overview cards should support Gemini-generated narratives."""

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

        response = self.client.get(reverse("dashboard:risk"))

        narratives = response.context["risk_card_narratives"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(narratives["cards"]["distribution"]["insight"], "Gemini distribution insight")
        self.assertEqual(narratives["cards"]["drivers"]["action"], "Gemini drivers action")
        self.assertEqual(narratives["cards"]["levels"]["insight"], "Gemini levels insight")
        self.assertEqual(narratives["cards"]["programmes"]["action"], "Gemini programmes action")
        self.assertEqual(narratives["cards"]["drivers"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["drivers"]["confidence"], "low")

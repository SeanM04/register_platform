"""Insights feature tests."""

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from ..test_support import DashboardFixtureMixin


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class InsightViewTests(DashboardFixtureMixin, TestCase):
    """Exercise institutional insights against the shared dashboard fixture."""

    def test_insights_view_supplies_story_payloads(self):
        """Insights page should expose distribution, faculty, driver, and action payloads."""

        response = self.client.get(reverse("dashboard:insights"))

        distribution_rows = response.context["risk_distribution_rows"]
        faculty_load_rows = response.context["faculty_load_rows"]
        faculty_pressure_rows = response.context["faculty_pressure_rows"]
        driver_rows = response.context["driver_rows"]
        confidence_rows = response.context["confidence_rows"]

        self.assertEqual(distribution_rows[0]["key"], "critical")
        self.assertEqual(distribution_rows[0]["count"], 0)
        self.assertEqual(distribution_rows[1]["key"], "high")
        self.assertEqual(distribution_rows[1]["count"], 1)
        self.assertEqual(distribution_rows[2]["key"], "moderate")
        self.assertEqual(distribution_rows[2]["count"], 1)
        self.assertEqual(distribution_rows[3]["key"], "low")
        self.assertEqual(distribution_rows[3]["count"], 0)

        self.assertEqual(faculty_load_rows[0]["label"], self.commerce_faculty.name)
        self.assertEqual(faculty_load_rows[0]["registrations"], 2)
        self.assertEqual(faculty_load_rows[0]["share_pct"], 67)
        self.assertEqual(faculty_load_rows[1]["label"], self.science_faculty.name)
        self.assertEqual(faculty_load_rows[1]["registrations"], 1)

        self.assertEqual(faculty_pressure_rows[0]["label"], self.commerce_faculty.name)
        self.assertEqual(faculty_pressure_rows[0]["high_risk"], 1)
        self.assertEqual(faculty_pressure_rows[0]["medium_risk"], 0)
        self.assertEqual(faculty_pressure_rows[1]["label"], self.science_faculty.name)
        self.assertEqual(faculty_pressure_rows[1]["high_risk"], 0)
        self.assertEqual(faculty_pressure_rows[1]["medium_risk"], 1)

        self.assertEqual(driver_rows[0]["label"], "Average 50-59%")
        self.assertEqual(driver_rows[0]["count"], 2)
        self.assertEqual(len(confidence_rows), 4)
        self.assertTrue(all(row["value"] > 0 for row in confidence_rows))

    def test_insights_view_respects_faculty_filter(self):
        """Insights page should narrow the story payloads to the selected faculty."""

        response = self.client.get(
            reverse("dashboard:insights"),
            {"faculty": self.science_faculty.name},
        )

        distribution_rows = response.context["risk_distribution_rows"]
        faculty_load_rows = response.context["faculty_load_rows"]
        faculty_pressure_rows = response.context["faculty_pressure_rows"]
        driver_rows = response.context["driver_rows"]

        self.assertEqual(response.context["flagged_total"], 0)
        self.assertEqual(faculty_load_rows[0]["label"], self.science_faculty.name)
        self.assertEqual(faculty_load_rows[0]["registrations"], 1)
        self.assertEqual(faculty_load_rows[0]["share_pct"], 100)
        self.assertEqual(len(faculty_pressure_rows), 0)
        self.assertEqual(distribution_rows[1]["count"], 0)
        self.assertEqual(distribution_rows[2]["count"], 0)
        self.assertEqual(distribution_rows[3]["count"], 1)
        self.assertEqual(driver_rows, [])

        scope_labels = [pill["label"] for pill in response.context["insight_scope_pills"]]
        self.assertEqual(scope_labels[0], "Filtered scope")
        self.assertIn(f"Faculty: {self.science_faculty.name}", scope_labels)
        self.assertNotIn("All faculties", scope_labels)

    def test_insights_view_supplies_rule_based_card_narratives_by_default(self):
        """Insights overview cards should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:insights"))

        narratives = response.context["insight_card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertIn("distribution", narratives["cards"])
        self.assertIn("faculty_load", narratives["cards"])
        self.assertIn("faculty_pressure", narratives["cards"])
        self.assertIn("drivers", narratives["cards"])
        self.assertTrue(narratives["cards"]["distribution"]["insight"])
        self.assertTrue(narratives["cards"]["drivers"]["action"])
        self.assertEqual(narratives["cards"]["distribution"]["severity"], "high")
        self.assertEqual(narratives["cards"]["faculty_load"]["confidence"], "low")

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.insights.ai_insights._request_insight_openai_narratives")
    def test_insights_view_uses_ai_card_narratives_when_available(self, mock_request):
        """Insights overview cards should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"distribution\\":{\\"insight\\":\\"AI distribution insight\\",\\"action\\":\\"AI distribution action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"},\\"faculty_load\\":{\\"insight\\":\\"AI load insight\\",\\"action\\":\\"AI load action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"faculty_pressure\\":{\\"insight\\":\\"AI pressure insight\\",\\"action\\":\\"AI pressure action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"},\\"drivers\\":{\\"insight\\":\\"AI driver insight\\",\\"action\\":\\"AI driver action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:insights"))

        narratives = response.context["insight_card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["distribution"]["insight"], "AI distribution insight")
        self.assertEqual(narratives["cards"]["faculty_load"]["action"], "AI load action")
        self.assertEqual(narratives["cards"]["faculty_pressure"]["insight"], "AI pressure insight")
        self.assertEqual(narratives["cards"]["drivers"]["action"], "AI driver action")
        self.assertEqual(narratives["cards"]["distribution"]["severity"], "high")
        self.assertEqual(narratives["cards"]["drivers"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.insights.ai_insights._request_insight_google_narratives")
    def test_insights_view_can_use_google_card_narratives(self, mock_request):
        """Insights overview cards should support Gemini-generated narratives."""

        mock_request.return_value = """
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "{\\"cards\\":{\\"distribution\\":{\\"insight\\":\\"Gemini distribution insight\\",\\"action\\":\\"Gemini distribution action\\"},\\"faculty_load\\":{\\"insight\\":\\"Gemini load insight\\",\\"action\\":\\"Gemini load action\\"},\\"faculty_pressure\\":{\\"insight\\":\\"Gemini pressure insight\\",\\"action\\":\\"Gemini pressure action\\"},\\"drivers\\":{\\"insight\\":\\"Gemini drivers insight\\",\\"action\\":\\"Gemini drivers action\\"}}}"
                            }
                        ]
                    }
                }
            ]
        }
        """

        response = self.client.get(reverse("dashboard:insights"))

        narratives = response.context["insight_card_narratives"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(narratives["cards"]["distribution"]["insight"], "Gemini distribution insight")
        self.assertEqual(narratives["cards"]["faculty_load"]["action"], "Gemini load action")
        self.assertEqual(narratives["cards"]["faculty_pressure"]["insight"], "Gemini pressure insight")
        self.assertEqual(narratives["cards"]["drivers"]["action"], "Gemini drivers action")
        self.assertEqual(narratives["cards"]["distribution"]["severity"], "high")
        self.assertEqual(narratives["cards"]["drivers"]["confidence"], "low")

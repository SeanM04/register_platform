"""Programme feature tests."""

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
class ProgrammeViewTests(DashboardFixtureMixin, TestCase):
    """Exercise the story-first programmes dashboard against the shared fixture."""

    def test_programme_view_renders_story_context(self):
        """Programme page should expose summary cards, chart rows, and the register."""

        response = self.client.get(reverse("dashboard:programme"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["summary_cards"]), 4)
        self.assertTrue(response.context["top_load_rows"])
        self.assertTrue(response.context["department_rows"])
        self.assertTrue(response.context["low_pass_rows"])
        self.assertTrue(response.context["performance_rows"])
        self.assertTrue(response.context["programme_rows"])

    def test_programme_view_respects_faculty_filter_for_story_rows(self):
        """Programme story rows should respect the selected faculty scope."""

        response = self.client.get(
            reverse("dashboard:programme"),
            {"faculty": self.science_faculty.name},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary_cards"][0]["value"], 1)
        self.assertEqual(len(response.context["top_load_rows"]), 1)
        self.assertEqual(response.context["top_load_rows"][0]["faculty"], self.science_faculty.name)
        self.assertEqual(response.context["scope_pills"][0]["label"], "Filtered programmes")

    def test_programme_metrics_endpoint_respects_faculty_filter(self):
        """Programme metrics JSON should still respect the selected faculty."""

        response = self.client.get(
            reverse("dashboard:programme-metrics"),
            {"faculty": self.science_faculty.name},
        )

        metrics = response.json()["metrics"]

        self.assertEqual(metrics["programmes"], 1)
        self.assertEqual(metrics["registrations"], 1)
        self.assertEqual(metrics["students"], 1)
        self.assertEqual(metrics["average_pass_rate"], "100%")

    def test_programme_view_supplies_rule_based_card_narratives_by_default(self):
        """Programme chart cards should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:programme"))

        narratives = response.context["programme_card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertIn("load", narratives["cards"])
        self.assertIn("departments", narratives["cards"])
        self.assertIn("quality", narratives["cards"])
        self.assertIn("performance", narratives["cards"])
        self.assertTrue(narratives["cards"]["load"]["insight"])
        self.assertTrue(narratives["cards"]["quality"]["action"])
        self.assertIn(narratives["cards"]["departments"]["confidence"], {"low", "medium", "high"})
        self.assertIn(narratives["cards"]["performance"]["severity"], {"stable", "medium", "high"})

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.programmes.ai_insights._request_programme_openai_narratives")
    def test_programme_view_uses_ai_card_narratives_when_available(self, mock_request):
        """Programme overview cards should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"load\\":{\\"insight\\":\\"AI load insight\\",\\"action\\":\\"AI load action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"},\\"departments\\":{\\"insight\\":\\"AI department insight\\",\\"action\\":\\"AI department action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"quality\\":{\\"insight\\":\\"AI quality insight\\",\\"action\\":\\"AI quality action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"},\\"performance\\":{\\"insight\\":\\"AI performance insight\\",\\"action\\":\\"AI performance action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:programme"))

        narratives = response.context["programme_card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["load"]["insight"], "AI load insight")
        self.assertEqual(narratives["cards"]["departments"]["action"], "AI department action")
        self.assertEqual(narratives["cards"]["quality"]["insight"], "AI quality insight")
        self.assertEqual(narratives["cards"]["performance"]["action"], "AI performance action")
        self.assertEqual(narratives["cards"]["load"]["severity"], "high")
        self.assertEqual(narratives["cards"]["load"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.programmes.ai_insights._request_programme_google_narratives")
    def test_programme_view_can_use_google_card_narratives(self, mock_request):
        """Programme overview cards should support Gemini-generated narratives."""

        mock_request.return_value = """
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "{\\"cards\\":{\\"load\\":{\\"insight\\":\\"Gemini load insight\\",\\"action\\":\\"Gemini load action\\"},\\"departments\\":{\\"insight\\":\\"Gemini department insight\\",\\"action\\":\\"Gemini department action\\"},\\"quality\\":{\\"insight\\":\\"Gemini quality insight\\",\\"action\\":\\"Gemini quality action\\"},\\"performance\\":{\\"insight\\":\\"Gemini performance insight\\",\\"action\\":\\"Gemini performance action\\"}}}"
                            }
                        ]
                    }
                }
            ]
        }
        """

        response = self.client.get(reverse("dashboard:programme"))

        narratives = response.context["programme_card_narratives"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(narratives["cards"]["load"]["insight"], "Gemini load insight")
        self.assertEqual(narratives["cards"]["departments"]["action"], "Gemini department action")
        self.assertEqual(narratives["cards"]["quality"]["insight"], "Gemini quality insight")
        self.assertEqual(narratives["cards"]["performance"]["action"], "Gemini performance action")
        self.assertIn(narratives["cards"]["load"]["severity"], {"stable", "medium", "high"})
        self.assertIn(narratives["cards"]["departments"]["confidence"], {"low", "medium", "high"})

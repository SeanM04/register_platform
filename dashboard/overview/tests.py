"""Tests for the story-first landing dashboard."""

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
class OverviewDashboardTests(DashboardFixtureMixin, TestCase):
    """Exercise the production-facing landing dashboard against real filtered data."""

    def test_overview_view_renders_story_context(self):
        """The landing page should expose story content, charts, and action cards."""

        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["summary_cards"]), 4)
        self.assertEqual(len(response.context["action_cards"]), 4)
        self.assertTrue(response.context["outcome_rows"])
        self.assertTrue(response.context["risk_distribution_rows"])
        self.assertTrue(response.context["faculty_load_rows"])
        self.assertTrue(response.context["progress_rows"])

    def test_overview_view_respects_faculty_filter_for_story_rows(self):
        """Landing-page charts and cards should respect the selected faculty scope."""

        response = self.client.get(
            reverse("dashboard:home"),
            {"faculty": self.science_faculty.name},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary_cards"][0]["value"], 1)
        self.assertEqual(len(response.context["faculty_load_rows"]), 1)
        self.assertEqual(response.context["faculty_load_rows"][0]["label"], self.science_faculty.name)
        self.assertEqual(response.context["scope_pills"][0]["label"], "Filtered overview")

    def test_overview_view_supplies_rule_based_card_narratives_by_default(self):
        """Landing-page chart cards should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:home"))

        narratives = response.context["overview_card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertIn("outcomes", narratives["cards"])
        self.assertIn("risk", narratives["cards"])
        self.assertIn("faculty", narratives["cards"])
        self.assertIn("progress", narratives["cards"])
        self.assertTrue(narratives["cards"]["outcomes"]["insight"])
        self.assertTrue(narratives["cards"]["outcomes"]["action"])
        self.assertIn(narratives["cards"]["faculty"]["confidence"], {"low", "medium", "high"})
        self.assertIn(narratives["cards"]["progress"]["severity"], {"stable", "medium", "high"})

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.overview.ai_insights._request_overview_openai_narratives")
    def test_overview_view_uses_ai_card_narratives_when_available(self, mock_request):
        """Landing-page overview cards should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"outcomes\\":{\\"insight\\":\\"AI outcomes insight\\",\\"action\\":\\"AI outcomes action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"risk\\":{\\"insight\\":\\"AI risk insight\\",\\"action\\":\\"AI risk action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"},\\"faculty\\":{\\"insight\\":\\"AI faculty insight\\",\\"action\\":\\"AI faculty action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"progress\\":{\\"insight\\":\\"AI progress insight\\",\\"action\\":\\"AI progress action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:home"))

        narratives = response.context["overview_card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["outcomes"]["insight"], "AI outcomes insight")
        self.assertEqual(narratives["cards"]["risk"]["action"], "AI risk action")
        self.assertEqual(narratives["cards"]["faculty"]["insight"], "AI faculty insight")
        self.assertEqual(narratives["cards"]["progress"]["action"], "AI progress action")
        self.assertEqual(narratives["cards"]["risk"]["severity"], "high")
        self.assertEqual(narratives["cards"]["risk"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.overview.ai_insights._request_overview_google_narratives")
    def test_overview_view_can_use_google_card_narratives(self, mock_request):
        """Landing-page overview cards should support Gemini-generated narratives."""

        mock_request.return_value = """
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "{\\"cards\\":{\\"outcomes\\":{\\"insight\\":\\"Gemini outcomes insight\\",\\"action\\":\\"Gemini outcomes action\\"},\\"risk\\":{\\"insight\\":\\"Gemini risk insight\\",\\"action\\":\\"Gemini risk action\\"},\\"faculty\\":{\\"insight\\":\\"Gemini faculty insight\\",\\"action\\":\\"Gemini faculty action\\"},\\"progress\\":{\\"insight\\":\\"Gemini progress insight\\",\\"action\\":\\"Gemini progress action\\"}}}"
                            }
                        ]
                    }
                }
            ]
        }
        """

        response = self.client.get(reverse("dashboard:home"))

        narratives = response.context["overview_card_narratives"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(narratives["cards"]["outcomes"]["insight"], "Gemini outcomes insight")
        self.assertEqual(narratives["cards"]["risk"]["action"], "Gemini risk action")
        self.assertEqual(narratives["cards"]["faculty"]["insight"], "Gemini faculty insight")
        self.assertEqual(narratives["cards"]["progress"]["action"], "Gemini progress action")
        self.assertIn(narratives["cards"]["outcomes"]["severity"], {"stable", "medium", "high"})
        self.assertIn(narratives["cards"]["faculty"]["confidence"], {"low", "medium", "high"})

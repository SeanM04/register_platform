"""Demographics feature tests."""

from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from ..test_support import DashboardFixtureMixin


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class DemographicViewTests(DashboardFixtureMixin, TestCase):
    """Exercise demographic analytics against the shared dashboard fixture."""

    def test_demographic_view_supplies_gender_location_and_programme_breakdowns(self):
        """Demographics page should expose grouped gender, location, and programme rows."""

        response = self.client.get(reverse("dashboard:demographic"))

        gender_rows = response.context["gender_rows"]
        location_rows = response.context["location_rows"]
        location_mix_rows = response.context["location_mix_rows"]
        location_map_rows = response.context["location_map_rows"]
        location_map_meta = response.context["location_map_meta"]
        programme_rows = response.context["programme_rows"]

        self.assertEqual(gender_rows[0]["label"], "Male")
        self.assertEqual(gender_rows[0]["count"], 1)
        self.assertEqual(gender_rows[0]["share"], "50%")
        self.assertEqual(gender_rows[1]["label"], "Female")
        self.assertEqual(gender_rows[1]["count"], 1)
        self.assertEqual(gender_rows[1]["share"], "50%")
        self.assertEqual(gender_rows[2]["label"], "Unspecified")
        self.assertEqual(gender_rows[2]["count"], 0)

        self.assertEqual(location_rows[0]["place"], "Bulawayo")
        self.assertEqual(location_rows[0]["count"], 1)
        self.assertEqual(location_rows[1]["place"], "Harare")
        self.assertEqual(location_rows[1]["count"], 1)
        self.assertEqual(location_mix_rows[0]["place"], "Bulawayo")
        self.assertEqual(location_mix_rows[0]["female"], 1)
        self.assertEqual(location_mix_rows[0]["total"], 1)
        self.assertEqual(location_mix_rows[1]["place"], "Harare")
        self.assertEqual(location_mix_rows[1]["male"], 1)
        self.assertEqual(location_mix_rows[1]["total"], 1)
        self.assertEqual(location_map_rows[0]["place"], "Bulawayo")
        self.assertEqual(location_map_rows[0]["province"], "Bulawayo")
        self.assertEqual(location_map_rows[0]["count"], 1)
        self.assertIn("lng", location_map_rows[0])
        self.assertIn("lat", location_map_rows[0])
        self.assertEqual(location_map_rows[1]["place"], "Harare")
        self.assertEqual(location_map_meta["mapped_places"], 2)
        self.assertEqual(location_map_meta["mapped_students"], 2)
        self.assertEqual(location_map_meta["unmapped_students"], 0)

        self.assertEqual(len(programme_rows), 2)
        self.assertEqual(programme_rows[0]["programme"], self.commerce_programme.name)
        self.assertEqual(programme_rows[0]["male"], 1)
        self.assertEqual(programme_rows[0]["female"], 0)
        self.assertEqual(programme_rows[0]["total"], 1)
        self.assertEqual(programme_rows[1]["programme"], self.science_programme.name)
        self.assertEqual(programme_rows[1]["male"], 0)
        self.assertEqual(programme_rows[1]["female"], 1)
        self.assertEqual(programme_rows[1]["total"], 1)

    def test_demographic_view_supplies_rule_based_card_narratives_by_default(self):
        """Demographics overview cards should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:demographic"))

        narratives = response.context["demographic_card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertIn("gender", narratives["cards"])
        self.assertIn("location", narratives["cards"])
        self.assertIn("location_mix", narratives["cards"])
        self.assertIn("programme", narratives["cards"])
        self.assertIn("origin_map", narratives["cards"])
        self.assertTrue(narratives["cards"]["gender"]["insight"])
        self.assertTrue(narratives["cards"]["gender"]["action"])
        self.assertEqual(narratives["cards"]["gender"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["gender"]["confidence"], "low")
        self.assertEqual(narratives["cards"]["origin_map"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["origin_map"]["confidence"], "low")

    def test_demographic_view_respects_faculty_filter(self):
        """Demographic rows should reflect the active faculty filter."""

        response = self.client.get(
            reverse("dashboard:demographic"),
            {"faculty": self.science_faculty.name},
        )

        gender_rows = response.context["gender_rows"]
        location_rows = response.context["location_rows"]
        location_mix_rows = response.context["location_mix_rows"]
        location_map_rows = response.context["location_map_rows"]
        programme_rows = response.context["programme_rows"]

        self.assertEqual(gender_rows[0]["count"], 0)
        self.assertEqual(gender_rows[1]["count"], 1)
        self.assertEqual(gender_rows[1]["share"], "100%")
        self.assertEqual(len(location_rows), 1)
        self.assertEqual(location_rows[0]["place"], "Bulawayo")
        self.assertEqual(len(location_mix_rows), 1)
        self.assertEqual(location_mix_rows[0]["place"], "Bulawayo")
        self.assertEqual(location_mix_rows[0]["female"], 1)
        self.assertEqual(len(location_map_rows), 1)
        self.assertEqual(location_map_rows[0]["place"], "Bulawayo")
        self.assertEqual(len(programme_rows), 1)
        self.assertEqual(programme_rows[0]["programme"], self.science_programme.name)
        self.assertEqual(programme_rows[0]["female"], 1)
        self.assertEqual(programme_rows[0]["total"], 1)

    def test_demographic_metrics_endpoint_respects_search_and_filters(self):
        """Demographic metrics should summarise the currently visible cohort."""

        response = self.client.get(
            reverse("dashboard:demographic-metrics"),
            {"faculty": self.science_faculty.name, "q": "informatics"},
        )

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["students"], 1)
        self.assertEqual(metrics["male"], 0)
        self.assertEqual(metrics["female"], 1)
        self.assertEqual(metrics["birth_locations"], 1)

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.demographics.ai_insights._request_demographic_openai_narratives")
    def test_demographic_view_uses_ai_card_narratives_when_available(self, mock_request):
        """Demographics overview cards should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"gender\\":{\\"insight\\":\\"AI gender insight\\",\\"action\\":\\"AI gender action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"location\\":{\\"insight\\":\\"AI location insight\\",\\"action\\":\\"AI location action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"location_mix\\":{\\"insight\\":\\"AI location mix insight\\",\\"action\\":\\"AI location mix action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"programme\\":{\\"insight\\":\\"AI programme insight\\",\\"action\\":\\"AI programme action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"high\\"},\\"origin_map\\":{\\"insight\\":\\"AI map insight\\",\\"action\\":\\"AI map action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:demographic"))

        narratives = response.context["demographic_card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["gender"]["insight"], "AI gender insight")
        self.assertEqual(narratives["cards"]["location"]["action"], "AI location action")
        self.assertEqual(narratives["cards"]["location_mix"]["insight"], "AI location mix insight")
        self.assertEqual(narratives["cards"]["programme"]["action"], "AI programme action")
        self.assertEqual(narratives["cards"]["origin_map"]["insight"], "AI map insight")
        self.assertEqual(narratives["cards"]["location"]["severity"], "medium")
        self.assertEqual(narratives["cards"]["programme"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.demographics.ai_insights._request_demographic_google_narratives")
    def test_demographic_view_can_use_google_card_narratives(self, mock_request):
        """Demographics overview cards should support Gemini-generated narratives."""

        mock_request.return_value = """
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "{\\"cards\\":{\\"gender\\":{\\"insight\\":\\"Gemini gender insight\\",\\"action\\":\\"Gemini gender action\\"},\\"location\\":{\\"insight\\":\\"Gemini location insight\\",\\"action\\":\\"Gemini location action\\"},\\"location_mix\\":{\\"insight\\":\\"Gemini location mix insight\\",\\"action\\":\\"Gemini location mix action\\"},\\"programme\\":{\\"insight\\":\\"Gemini programme insight\\",\\"action\\":\\"Gemini programme action\\"},\\"origin_map\\":{\\"insight\\":\\"Gemini map insight\\",\\"action\\":\\"Gemini map action\\"}}}"
                            }
                        ]
                    }
                }
            ]
        }
        """

        response = self.client.get(reverse("dashboard:demographic"))

        narratives = response.context["demographic_card_narratives"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(narratives["cards"]["gender"]["insight"], "Gemini gender insight")
        self.assertEqual(narratives["cards"]["location"]["action"], "Gemini location action")
        self.assertEqual(narratives["cards"]["location_mix"]["insight"], "Gemini location mix insight")
        self.assertEqual(narratives["cards"]["programme"]["action"], "Gemini programme action")
        self.assertEqual(narratives["cards"]["origin_map"]["insight"], "Gemini map insight")
        self.assertEqual(narratives["cards"]["gender"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["gender"]["confidence"], "low")

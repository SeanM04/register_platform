"""Programme feature tests."""

import urllib.error
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

    def test_programme_view_renders_lightweight_shell_context(self):
        """Programme page should render a fast shell without the heavy story payload."""

        response = self.client.get(reverse("dashboard:programme"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["summary_cards"]), 4)
        self.assertTrue(response.context["scope_pills"])
        self.assertNotIn("top_load_rows", response.context)
        self.assertNotIn("department_rows", response.context)
        self.assertNotIn("low_pass_rows", response.context)
        self.assertNotIn("performance_rows", response.context)
        self.assertNotIn("programme_rows", response.context)

    def test_programme_view_respects_faculty_filter_for_scope_pills(self):
        """Programme shell should still expose the active filter scope."""

        response = self.client.get(
            reverse("dashboard:programme"),
            {"faculty": self.science_faculty.name},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope_pills"][0]["label"], "Filtered programmes")
        self.assertIn(
            {"label": f"Faculty: {self.science_faculty.name}", "variant": "scope"},
            response.context["scope_pills"],
        )

    def test_programme_payload_endpoint_respects_faculty_filter(self):
        """Programme payload JSON should still respect the selected faculty."""

        response = self.client.get(
            reverse("dashboard:programme-payload"),
            {"faculty": self.science_faculty.name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()

        self.assertEqual(len(payload["programme_rows"]), 1)
        self.assertEqual(payload["top_load_rows"][0]["faculty"], self.science_faculty.name)
        self.assertEqual(payload["register_meta"]["visible_count"], 1)
        self.assertEqual(payload["top_load_rows"][0]["axis_label"], self.science_programme.code)

    def test_programme_payload_endpoint_sorts_programme_rows_by_query_parameters(self):
        """Programme register rows should respect sort and direction query parameters."""

        response = self.client.get(
            reverse("dashboard:programme-payload"),
            {"sort": "registrations", "direction": "desc"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()
        programme_rows = payload["programme_rows"]

        self.assertGreaterEqual(len(programme_rows), 2)
        self.assertEqual(programme_rows[0]["name"], self.commerce_programme.name)
        self.assertEqual(programme_rows[1]["name"], self.science_programme.name)

        response = self.client.get(
            reverse("dashboard:programme-payload"),
            {"sort": "average_mark", "direction": "asc"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()
        programme_rows = payload["programme_rows"]

        self.assertGreaterEqual(len(programme_rows), 2)
        self.assertEqual(programme_rows[0]["name"], self.commerce_programme.name)
        self.assertEqual(programme_rows[1]["name"], self.science_programme.name)

    def test_programme_payload_exposes_compact_axis_labels_for_story_charts(self):
        """Programme chart payloads should include short axis labels for cramped horizontal charts."""

        response = self.client.get(
            reverse("dashboard:programme-payload"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()

        self.assertTrue(payload["top_load_rows"])
        self.assertTrue(payload["department_rows"])
        self.assertTrue(
            all(row["axis_label"] == row["code"] for row in payload["top_load_rows"] if row.get("code"))
        )
        self.assertTrue(payload["department_rows"][0]["axis_label"])
        self.assertNotEqual(payload["department_rows"][0]["axis_label"], payload["department_rows"][0]["department"])

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

    def test_programme_narratives_endpoint_supplies_rule_based_copy_by_default(self):
        """Programme chart narratives should expose deterministic copy when AI is off."""

        response = self.client.get(
            reverse("dashboard:programme-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        narratives = response.json()["card_narratives"]
        diagnostics = response.json()["diagnostics"]

        self.assertEqual(narratives["source"], "rules")
        self.assertEqual(diagnostics["returned_source"], "rules")
        self.assertEqual(diagnostics["status"], "rules")
        self.assertEqual(diagnostics["fallback_reason"], "provider_rules_configured")
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
    def test_programme_narratives_endpoint_uses_ai_copy_when_available(self, mock_request):
        """Programme overview narratives should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"load\\":{\\"insight\\":\\"AI load insight\\",\\"action\\":\\"AI load action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"},\\"departments\\":{\\"insight\\":\\"AI department insight\\",\\"action\\":\\"AI department action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"quality\\":{\\"insight\\":\\"AI quality insight\\",\\"action\\":\\"AI quality action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"},\\"performance\\":{\\"insight\\":\\"AI performance insight\\",\\"action\\":\\"AI performance action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"}}}"
        }
        """

        response = self.client.get(
            reverse("dashboard:programme-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(diagnostics["returned_source"], "openai")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "openai")
        self.assertEqual(narratives["cards"]["load"]["insight"], "AI load insight")
        self.assertEqual(narratives["cards"]["departments"]["action"], "AI department action")
        self.assertEqual(narratives["cards"]["quality"]["insight"], "AI quality insight")
        self.assertEqual(narratives["cards"]["performance"]["action"], "AI performance action")
        self.assertEqual(narratives["cards"]["load"]["severity"], "high")
        self.assertEqual(narratives["cards"]["load"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.programmes.ai_insights._request_programme_google_narratives")
    def test_programme_narratives_endpoint_can_use_google_card_narratives(self, mock_request):
        """Programme overview narratives should support Gemini-generated copy."""

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

        response = self.client.get(
            reverse("dashboard:programme-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(diagnostics["returned_source"], "google")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(narratives["cards"]["load"]["insight"], "Gemini load insight")
        self.assertEqual(narratives["cards"]["departments"]["action"], "Gemini department action")
        self.assertEqual(narratives["cards"]["quality"]["insight"], "Gemini quality insight")
        self.assertEqual(narratives["cards"]["performance"]["action"], "Gemini performance action")
        self.assertIn(narratives["cards"]["load"]["severity"], {"stable", "medium", "high"})
        self.assertIn(narratives["cards"]["departments"]["confidence"], {"low", "medium", "high"})

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.programmes.ai_insights._request_programme_google_narratives")
    def test_programme_narratives_endpoint_reports_structured_fallback_diagnostics_when_google_fails(self, mock_request):
        """Programme narratives should expose a stable fallback reason when Gemini cannot be reached."""

        mock_request.side_effect = OSError("WinError 10013 network blocked")

        response = self.client.get(
            reverse("dashboard:programme-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "rules")
        self.assertEqual(diagnostics["returned_source"], "rules")
        self.assertEqual(diagnostics["status"], "fallback")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(diagnostics["fallback_reason"], "google_os_error")
        self.assertIn("Google Gemini", diagnostics["message"])

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.programmes.ai_insights._request_programme_google_narratives")
    def test_programme_narratives_endpoint_reports_rate_limit_diagnostics_for_google_429(self, mock_request):
        """Programme narratives should explain when Gemini rejects the request with a quota/rate-limit response."""

        mock_request.side_effect = urllib.error.HTTPError(
            "https://example.com",
            429,
            "Too Many Requests",
            None,
            None,
        )

        response = self.client.get(
            reverse("dashboard:programme-narratives"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        diagnostics = response.json()["diagnostics"]

        self.assertEqual(diagnostics["status"], "fallback")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(diagnostics["fallback_reason"], "google_rate_limited")
        self.assertIn("quota or request limits", diagnostics["message"])

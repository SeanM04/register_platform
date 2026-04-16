"""Tests for the story-first landing dashboard."""

import json
import urllib.error
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Registration
from ..test_support import DashboardFixtureMixin
from .ai_insights import build_overview_fact_pack
from .services import _calculate_first_year_retention


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class OverviewDashboardTests(DashboardFixtureMixin, TestCase):
    """Exercise the production-facing landing dashboard against real filtered data."""

    def setUp(self):
        """Clear cross-request caches so each test starts from a clean scope."""

        super().setUp()
        cache.clear()

    def test_overview_view_renders_shell_context(self):
        """The landing page should render a lightweight shell before async hydration."""

        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["summary_cards"]), 8)
        self.assertEqual(response.context["summary_cards"][0]["value"], "--")
        self.assertEqual(len(response.context["action_cards"]), 4)
        self.assertNotIn("outcome_rows", response.context)
        self.assertNotIn("risk_distribution_rows", response.context)
        self.assertNotIn("faculty_load_rows", response.context)
        self.assertNotIn("progress_rows", response.context)
        self.assertNotIn("overview_card_narratives", response.context)
        self.assertNotContains(response, 'id="home-chapter-one-summary"', html=False)
        self.assertNotContains(response, 'id="home-chapter-two-summary"', html=False)

    def test_overview_payload_endpoint_supplies_story_data(self):
        """The landing-page payload endpoint should return the heavy chart and action data."""

        response = self.client.get(reverse("dashboard:home-payload"))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        summary_cards = data["summary_cards"]
        outcome_rows = data["outcome_rows"]
        risk_distribution_rows = data["risk_distribution_rows"]
        faculty_load_rows = data["faculty_load_rows"]
        progress_rows = data["progress_rows"]
        action_cards = data["action_cards"]

        self.assertEqual(len(summary_cards), 8)
        self.assertEqual(summary_cards[0]["key"], "enrolled")
        self.assertEqual(summary_cards[0]["value"], 2)
        completion_card = next(card for card in summary_cards if card["key"] == "completion_rate")
        self.assertEqual(completion_card["value"], "33%")
        self.assertTrue(outcome_rows)
        self.assertTrue(risk_distribution_rows)
        self.assertTrue(faculty_load_rows)
        self.assertTrue(progress_rows)
        self.assertEqual(len(action_cards), 4)

    def test_overview_drilldown_endpoint_returns_student_rows_for_outcome_slices(self):
        """Outcome drill-downs should return a student table instead of a summary-only popup."""

        response = self.client.get(
            reverse("dashboard:home-drilldown"),
            {"chart": "outcomes", "bucket": "failed"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["title"], "Failed Students")
        self.assertEqual(
            [column["key"] for column in data["columns"]],
            [
                "name",
                "registration_number",
                "programme",
            ],
        )
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["name"], self.student_primary.full_name)
        self.assertEqual(data["rows"][0]["registration_number"], self.student_primary.registration_number)
        self.assertEqual(
            data["rows"][0]["detail_url"],
            reverse("dashboard:student-detail", args=[self.student_primary.registration_number.lower()]),
        )

    def test_overview_drilldown_endpoint_returns_pagination_metadata(self):
        response = self.client.get(
            reverse("dashboard:home-drilldown"),
            {"chart": "outcomes", "bucket": "failed"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 100)
        self.assertEqual(data["page_count"], 1)
        self.assertEqual(data["total_count"], 1)

    def test_overview_drilldown_endpoint_returns_student_rows_for_risk_bars(self):
        """Risk drill-downs should return the matching student cohort rows for the clicked bar."""

        payload = self.client.get(reverse("dashboard:home-payload")).json()
        selected_band = next(row for row in payload["risk_distribution_rows"] if row["count"] > 0)

        response = self.client.get(
            reverse("dashboard:home-drilldown"),
            {"chart": "risk_distribution", "bucket": selected_band["key"]},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["title"], f"{selected_band['label']} Students")
        self.assertEqual(
            [column["key"] for column in data["columns"]],
            [
                "name",
                "registration_number",
                "programme",
            ],
        )
        self.assertTrue(data["rows"])
        self.assertIn("detail_url", data["rows"][0])
        self.assertNotIn("risk_score", data["rows"][0])
        self.assertNotIn("risk_level", data["rows"][0])

    def test_overview_drilldown_rows_only_return_minimal_fields(self):
        """Drill-down rows should only include the minimal fields needed for the table."""

        payload = self.client.get(reverse("dashboard:home-payload")).json()
        selected_band = next(row for row in payload["risk_distribution_rows"] if row["count"] > 0)

        response = self.client.get(
            reverse("dashboard:home-drilldown"),
            {"chart": "risk_distribution", "bucket": selected_band["key"]},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["rows"])
        for row in data["rows"]:
            self.assertEqual(
                set(row.keys()),
                {"name", "registration_number", "programme", "detail_url"},
            )

    def test_overview_drilldown_payload_is_cached(self):
        """The overview drilldown payload should be cached by filter scope, chart, bucket, page, and size."""

        from django.test import RequestFactory
        from .services import _build_overview_drilldown_cache_key, build_overview_drilldown_data

        cache.clear()
        request = RequestFactory().get(
            reverse("dashboard:home-drilldown"),
            {"chart": "outcomes", "bucket": "failed"},
        )

        data = build_overview_drilldown_data(request, "outcomes", "failed")
        self.assertTrue(data["rows"])

        cache_key = _build_overview_drilldown_cache_key(request, "outcomes", "failed", 1, 100)
        self.assertIsNotNone(cache.get(cache_key))

    def test_overview_drilldown_caches_can_be_cleared(self):
        """Individual drilldown caches should be deletable without affecting other levels."""

        from django.test import RequestFactory
        from .services import _build_overview_drilldown_cache_key, build_overview_drilldown_data

        cache.clear()
        request = RequestFactory().get(
            reverse("dashboard:home-drilldown"),
            {"chart": "outcomes", "bucket": "failed"},
        )

        _ = build_overview_drilldown_data(request, "outcomes", "failed")
        cache_key = _build_overview_drilldown_cache_key(request, "outcomes", "failed", 1, 100)
        self.assertIsNotNone(cache.get(cache_key))

        cache.delete(cache_key)
        self.assertIsNone(cache.get(cache_key))

    def test_overview_drilldown_endpoint_rejects_unknown_chart_requests(self):
        """Invalid drill-down requests should fail fast with a clear client error."""

        response = self.client.get(
            reverse("dashboard:home-drilldown"),
            {"chart": "unknown", "bucket": "anything"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    @patch("builtins.print")
    def test_overview_payload_endpoint_does_not_emit_debug_output(self, mock_print):
        """The landing-page payload should stay quiet and avoid debug terminal noise."""

        response = self.client.get(reverse("dashboard:home-payload"))

        self.assertEqual(response.status_code, 200)
        mock_print.assert_not_called()

    def test_overview_payload_endpoint_respects_faculty_filter_for_story_rows(self):
        """Landing-page payload and metrics should respect the selected faculty scope."""

        response = self.client.get(
            reverse("dashboard:home-payload"),
            {"faculty": self.science_faculty.name},
        )

        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["summary_cards"][0]["value"], 1)
        self.assertEqual(len(data["faculty_load_rows"]), 1)
        self.assertEqual(data["faculty_load_rows"][0]["label"], self.science_faculty.name)

        metrics_response = self.client.get(
            reverse("dashboard:home-metrics"),
            {"faculty": self.science_faculty.name},
        )

        metrics = metrics_response.json()["metrics"]
        self.assertEqual(metrics["enrolled"], 1)
        self.assertEqual(metrics["registered"], 1)

    def test_overview_narratives_endpoint_supplies_rule_based_card_narratives_by_default(self):
        """Landing-page chart cards should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:home-narratives"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "rules")
        self.assertEqual(diagnostics["returned_source"], "rules")
        self.assertEqual(diagnostics["status"], "rules")
        self.assertEqual(diagnostics["fallback_reason"], "provider_rules_configured")
        self.assertIn("outcomes", narratives["cards"])
        self.assertIn("risk", narratives["cards"])
        self.assertIn("faculty", narratives["cards"])
        self.assertIn("progress", narratives["cards"])
        self.assertTrue(narratives["cards"]["outcomes"]["insight"])
        self.assertTrue(narratives["cards"]["outcomes"]["action"])
        self.assertIn(narratives["cards"]["faculty"]["confidence"], {"low", "medium", "high"})
        self.assertIn(narratives["cards"]["progress"]["severity"], {"stable", "medium", "high"})

    def test_overview_fact_pack_stays_compact_for_default_scope(self):
        """The broad overview scope should send a compact fact pack to the AI provider."""

        payload = self.client.get(reverse("dashboard:home-payload")).json()
        fact_pack = build_overview_fact_pack(payload)
        serialized_fact_pack = json.dumps(fact_pack, sort_keys=True)

        self.assertNotIn("rows", fact_pack["outcomes"])
        self.assertNotIn("rows", fact_pack["risk"])
        self.assertNotIn("rows", fact_pack["progress"])
        self.assertLess(len(serialized_fact_pack), 1300)

    def test_first_year_retention_uses_a_single_batched_history_lookup(self):
        """Retention calculation should avoid per-student history queries for the home dashboard."""

        registrations = list(Registration.objects.all())

        with self.assertNumQueries(1):
            retention = _calculate_first_year_retention(registrations)

        self.assertEqual(retention, "50%")

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.overview.ai_insights._request_overview_openai_narratives")
    def test_overview_narratives_endpoint_uses_ai_card_narratives_when_available(self, mock_request):
        """Landing-page overview cards should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"outcomes\\":{\\"insight\\":\\"AI outcomes insight\\",\\"action\\":\\"AI outcomes action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"risk\\":{\\"insight\\":\\"AI risk insight\\",\\"action\\":\\"AI risk action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"},\\"faculty\\":{\\"insight\\":\\"AI faculty insight\\",\\"action\\":\\"AI faculty action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"progress\\":{\\"insight\\":\\"AI progress insight\\",\\"action\\":\\"AI progress action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:home-narratives"))

        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(diagnostics["returned_source"], "openai")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "openai")
        self.assertEqual(narratives["cards"]["outcomes"]["insight"], "AI outcomes insight")
        self.assertEqual(narratives["cards"]["risk"]["action"], "AI risk action")
        self.assertEqual(narratives["cards"]["faculty"]["insight"], "AI faculty insight")
        self.assertEqual(narratives["cards"]["progress"]["action"], "AI progress action")
        self.assertEqual(narratives["cards"]["risk"]["severity"], "high")
        self.assertEqual(narratives["cards"]["risk"]["confidence"], "high")

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="auto",
        OPENAI_INSIGHTS_ENABLED=False,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.overview.ai_insights._request_overview_openai_narratives")
    def test_overview_narratives_endpoint_uses_openai_when_global_ai_is_enabled_in_auto_mode(self, mock_request):
        """The global AI flag should still allow OpenAI narratives when provider selection is auto."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"outcomes\\":{\\"insight\\":\\"AI outcomes insight\\",\\"action\\":\\"AI outcomes action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"risk\\":{\\"insight\\":\\"AI risk insight\\",\\"action\\":\\"AI risk action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"},\\"faculty\\":{\\"insight\\":\\"AI faculty insight\\",\\"action\\":\\"AI faculty action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"progress\\":{\\"insight\\":\\"AI progress insight\\",\\"action\\":\\"AI progress action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:home-narratives"))

        narratives = response.json()["card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["outcomes"]["insight"], "AI outcomes insight")
        self.assertEqual(narratives["cards"]["progress"]["action"], "AI progress action")

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.overview.ai_insights._request_overview_openai_narratives")
    def test_overview_narratives_endpoint_reuses_cached_openai_copy_for_the_same_scope(self, mock_request):
        """A successful AI narrative should be reused for the same scope instead of falling back on the next hit."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"outcomes\\":{\\"insight\\":\\"AI outcomes insight\\",\\"action\\":\\"AI outcomes action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"risk\\":{\\"insight\\":\\"AI risk insight\\",\\"action\\":\\"AI risk action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"high\\"},\\"faculty\\":{\\"insight\\":\\"AI faculty insight\\",\\"action\\":\\"AI faculty action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"progress\\":{\\"insight\\":\\"AI progress insight\\",\\"action\\":\\"AI progress action\\",\\"severity\\":\\"high\\",\\"confidence\\":\\"medium\\"}}}"
        }
        """

        first_response = self.client.get(reverse("dashboard:home-narratives"))
        self.assertEqual(first_response.json()["card_narratives"]["source"], "openai")

        mock_request.reset_mock()

        second_response = self.client.get(reverse("dashboard:home-narratives"))
        narratives = second_response.json()["card_narratives"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(narratives["cards"]["faculty"]["insight"], "AI faculty insight")
        mock_request.assert_not_called()

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.overview.ai_insights._request_overview_google_narratives")
    def test_overview_narratives_endpoint_can_use_google_card_narratives(self, mock_request):
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

        response = self.client.get(reverse("dashboard:home-narratives"))

        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(diagnostics["returned_source"], "google")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(narratives["cards"]["outcomes"]["insight"], "Gemini outcomes insight")
        self.assertEqual(narratives["cards"]["risk"]["action"], "Gemini risk action")
        self.assertEqual(narratives["cards"]["faculty"]["insight"], "Gemini faculty insight")
        self.assertEqual(narratives["cards"]["progress"]["action"], "Gemini progress action")
        self.assertIn(narratives["cards"]["outcomes"]["severity"], {"stable", "medium", "high"})
        self.assertIn(narratives["cards"]["faculty"]["confidence"], {"low", "medium", "high"})

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.overview.ai_insights._request_overview_google_narratives")
    def test_overview_narratives_endpoint_reports_structured_fallback_diagnostics_when_google_fails(self, mock_request):
        """Overview narratives should expose a stable fallback reason when Gemini cannot be reached."""

        mock_request.side_effect = OSError("WinError 10013 network blocked")

        response = self.client.get(reverse("dashboard:home-narratives"))

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
    @patch("dashboard.overview.ai_insights._request_overview_google_narratives")
    def test_overview_narratives_endpoint_reports_rate_limit_diagnostics_for_google_429(self, mock_request):
        """Overview narratives should explain when Gemini rejects the request with a quota/rate-limit response."""

        mock_request.side_effect = urllib.error.HTTPError(
            "https://example.com",
            429,
            "Too Many Requests",
            None,
            None,
        )

        response = self.client.get(reverse("dashboard:home-narratives"))

        diagnostics = response.json()["diagnostics"]

        self.assertEqual(diagnostics["status"], "fallback")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(diagnostics["fallback_reason"], "google_rate_limited")
        self.assertIn("quota or request limits", diagnostics["message"])

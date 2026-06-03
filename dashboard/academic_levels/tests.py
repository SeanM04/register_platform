"""Academic-level feature tests."""

import urllib.error
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import AcademicPeriod, CourseResult, Registration, Student
from ..test_support import DashboardFixtureMixin


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class AcademicLevelViewTests(DashboardFixtureMixin, TestCase):
    """Exercise academic-level analytics and AI narrative fallbacks."""

    def setUp(self):
        """Clear dashboard caches so each academic-level test starts from a clean scope."""

        super().setUp()
        cache.clear()

    def test_academic_level_view_renders_lightweight_shell(self):
        """The first academic-level render should return a lightweight shell context."""

        response = self.client.get(reverse("dashboard:academic-level"))

        self.assertEqual(response.context["summary_cards"][0]["value"], "--")
        self.assertNotIn("level_rows", response.context)
        self.assertNotIn("level_chart_rows", response.context)
        self.assertContains(response, reverse("dashboard:academic-level-payload"))
        self.assertNotContains(response, "Top 5 programmes by enrolment chart")
        self.assertNotContains(response, "Back to top 5")

    def test_academic_level_payload_supplies_graph_breakdowns(self):
        """Academic level payload should expose pass, gender, and programme deep-dive data."""

        response = self.client.get(reverse("dashboard:academic-level-payload"))
        payload = response.json()

        level_rows = payload["level_rows"]
        level_chart_rows = payload["level_chart_rows"]
        gender_rows = payload["gender_performance_rows"]
        programme_rows = payload["programme_performance_rows"]

        self.assertEqual(level_rows[0]["pass_rate_value"], 100)
        self.assertFalse(level_rows[0]["below_target"])
        self.assertEqual(level_rows[1]["pass_rate_value"], 0)
        self.assertTrue(level_rows[1]["below_target"])
        self.assertEqual(level_chart_rows[0]["level"], "Year 1 Semester 1")
        self.assertEqual(level_chart_rows[0]["pass_rate"], "100%")
        self.assertEqual(level_chart_rows[0]["top_programme"], self.commerce_programme.name)
        commerce_breakdown = next(
            row for row in level_chart_rows[0]["programme_breakdown"] if row["programme"] == self.commerce_programme.name
        )
        self.assertEqual(commerce_breakdown["registrations"], 1)
        self.assertEqual(level_chart_rows[1]["level"], "Year 1 Semester 2")
        self.assertEqual(level_chart_rows[1]["pass_rate"], "0%")

        self.assertEqual(gender_rows[0]["label"], "Male")
        self.assertEqual(gender_rows[0]["pass_rate"], "100%")
        self.assertEqual(gender_rows[1]["label"], "Female")
        self.assertEqual(gender_rows[1]["pass_rate"], "50%")
        self.assertEqual(gender_rows[1]["average_mark"], 59)

        self.assertEqual(programme_rows[0]["programme"], self.science_programme.name)
        self.assertEqual(programme_rows[0]["pass_rate"], "100%")
        self.assertEqual(programme_rows[0]["level_breakdown"][0]["level"], "Year 1 Semester 1")
        self.assertEqual(programme_rows[0]["level_breakdown"][0]["registrations"], 1)
        self.assertEqual(programme_rows[1]["programme"], self.commerce_programme.name)
        self.assertEqual(programme_rows[1]["lead_level"], "Year 1 Semester 2")

    def test_academic_level_payload_breakdowns_follow_faculty_filter(self):
        """The academic-level payload should respect active faculty filters."""

        response = self.client.get(
            reverse("dashboard:academic-level-payload"),
            {"faculty": self.science_faculty.name},
        )
        payload = response.json()

        level_rows = payload["level_rows"]
        level_chart_rows = payload["level_chart_rows"]
        gender_rows = payload["gender_performance_rows"]
        programme_rows = payload["programme_performance_rows"]

        self.assertEqual(len(level_rows), 1)
        self.assertEqual(level_chart_rows[0]["level"], "Year 1 Semester 1")
        self.assertEqual(level_chart_rows[0]["pass_rate"], "100%")
        self.assertEqual(level_chart_rows[0]["programme_breakdown"][0]["programme"], self.science_programme.name)
        self.assertEqual(gender_rows[0]["students"], 0)
        self.assertEqual(gender_rows[1]["students"], 1)
        self.assertEqual(gender_rows[1]["pass_rate"], "100%")
        self.assertEqual(len(programme_rows), 1)
        self.assertEqual(programme_rows[0]["programme"], self.science_programme.name)

    def test_academic_level_metrics_return_summary_values(self):
        """Academic-level metrics should expose KPI values and the lightweight story payload."""

        response = self.client.get(reverse("dashboard:academic-level-metrics"))
        payload = response.json()
        metrics = payload["metrics"]
        story_payload = payload["story_payload"]

        self.assertEqual(metrics["levels"], 2)
        self.assertEqual(metrics["registrations"], 3)
        self.assertEqual(metrics["students"], 3)
        self.assertEqual(metrics["average_pass_rate"], "75%")
        self.assertEqual(story_payload["level_rows"][0]["level"], "Year 1 Semester 1")
        self.assertEqual(story_payload["gender_rows"][0]["label"], "Male")
        self.assertEqual(story_payload["programme_rows"][0]["programme"], self.commerce_programme.name)

    def test_academic_level_payload_rebases_imported_stage_labels_like_student_detail(self):
        student = Student.objects.create(
            registration_number="REG778",
            first_names="Academic",
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
        registration = Registration.objects.create(
            external_id=778,
            student=student,
            programme=self.science_programme,
            period=year_two_period,
            decision="repeat",
            carrying=1,
        )
        CourseResult.objects.create(
            registration=registration,
            course=self.course,
            mark=44,
        )

        payload = self.client.get(reverse("dashboard:academic-level-payload")).json()
        target_row = next(row for row in payload["level_rows"] if row["level"] == "Year 1 Semester 1")

        self.assertEqual(target_row["registrations"], 2)

    def test_academic_level_payload_supplies_rule_based_card_narratives_by_default(self):
        """Academic-level payload should have deterministic narratives when AI insights are disabled."""

        response = self.client.get(reverse("dashboard:academic-level-payload"))
        payload = response.json()

        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "rules")
        self.assertEqual(diagnostics["returned_source"], "rules")
        self.assertEqual(diagnostics["status"], "rules")
        self.assertEqual(diagnostics["fallback_reason"], "provider_rules_configured")
        self.assertIn("gender", narratives["cards"])
        self.assertIn("top_enrolment", narratives["cards"])
        self.assertIn("pass_trend", narratives["cards"])
        self.assertTrue(narratives["cards"]["gender"]["insight"])
        self.assertTrue(narratives["cards"]["gender"]["action"])
        self.assertEqual(narratives["cards"]["gender"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["gender"]["confidence"], "low")
        self.assertEqual(narratives["cards"]["top_enrolment"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["top_enrolment"]["confidence"], "low")
        self.assertEqual(narratives["cards"]["pass_trend"]["severity"], "high")
        self.assertEqual(narratives["cards"]["pass_trend"]["confidence"], "low")

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.academic_levels.ai_insights._request_academic_level_openai_narratives")
    def test_academic_level_payload_uses_ai_card_narratives_when_available(self, mock_request):
        """Academic-level payload should prefer AI-written narratives when the Responses API succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"gender\\":{\\"insight\\":\\"AI gender insight\\",\\"action\\":\\"AI gender action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"top_enrolment\\":{\\"insight\\":\\"AI enrolment insight\\",\\"action\\":\\"AI enrolment action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"pass_trend\\":{\\"insight\\":\\"AI pass insight\\",\\"action\\":\\"AI pass action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:academic-level-payload"))
        payload = response.json()

        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(diagnostics["returned_source"], "openai")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "openai")
        self.assertEqual(narratives["cards"]["gender"]["insight"], "AI gender insight")
        self.assertEqual(narratives["cards"]["top_enrolment"]["action"], "AI enrolment action")
        self.assertEqual(narratives["cards"]["pass_trend"]["insight"], "AI pass insight")
        self.assertEqual(narratives["cards"]["gender"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["gender"]["confidence"], "medium")
        self.assertEqual(narratives["cards"]["top_enrolment"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["top_enrolment"]["confidence"], "medium")
        self.assertEqual(narratives["cards"]["pass_trend"]["severity"], "high")
        self.assertEqual(narratives["cards"]["pass_trend"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.academic_levels.ai_insights._request_academic_level_google_narratives")
    def test_academic_level_payload_can_use_google_card_narratives(self, mock_request):
        """Academic-level payload should support Gemini-generated narratives when Google is selected."""

        mock_request.return_value = """
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "{\\"cards\\":{\\"gender\\":{\\"insight\\":\\"Gemini gender insight\\",\\"action\\":\\"Gemini gender action\\"},\\"top_enrolment\\":{\\"insight\\":\\"Gemini enrolment insight\\",\\"action\\":\\"Gemini enrolment action\\"},\\"pass_trend\\":{\\"insight\\":\\"Gemini pass insight\\",\\"action\\":\\"Gemini pass action\\"}}}"
                            }
                        ]
                    }
                }
            ]
        }
        """

        response = self.client.get(reverse("dashboard:academic-level-payload"))
        payload = response.json()

        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(diagnostics["returned_source"], "google")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(narratives["cards"]["gender"]["insight"], "Gemini gender insight")
        self.assertEqual(narratives["cards"]["top_enrolment"]["action"], "Gemini enrolment action")
        self.assertEqual(narratives["cards"]["pass_trend"]["insight"], "Gemini pass insight")
        self.assertEqual(narratives["cards"]["gender"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["gender"]["confidence"], "low")
        self.assertEqual(narratives["cards"]["top_enrolment"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["top_enrolment"]["confidence"], "low")
        self.assertEqual(narratives["cards"]["pass_trend"]["severity"], "high")
        self.assertEqual(narratives["cards"]["pass_trend"]["confidence"], "low")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.academic_levels.ai_insights._request_academic_level_google_narratives")
    def test_academic_level_payload_reports_rate_limit_diagnostics_for_google_429(self, mock_request):
        """Academic-level diagnostics should explain when Gemini rejects the request with a quota/rate-limit response."""

        mock_request.side_effect = urllib.error.HTTPError(
            "https://example.com",
            429,
            "Too Many Requests",
            None,
            None,
        )

        response = self.client.get(reverse("dashboard:academic-level-payload"))
        payload = response.json()

        diagnostics = payload["diagnostics"]
        narratives = payload["card_narratives"]

        self.assertEqual(narratives["source"], "rules")
        self.assertEqual(diagnostics["status"], "fallback")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(diagnostics["fallback_reason"], "google_rate_limited")
        self.assertIn("quota or request limits", diagnostics["message"])

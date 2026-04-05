"""Academic-level feature tests."""

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
class AcademicLevelViewTests(DashboardFixtureMixin, TestCase):
    """Exercise academic-level analytics and AI narrative fallbacks."""

    def test_academic_level_view_supplies_graph_breakdowns(self):
        """Academic level analytics should expose pass, gender, and programme deep-dive data."""

        response = self.client.get(reverse("dashboard:academic-level"))

        level_rows = response.context["level_rows"]
        level_chart_rows = response.context["level_chart_rows"]
        gender_rows = response.context["gender_performance_rows"]
        programme_rows = response.context["programme_performance_rows"]

        self.assertEqual(level_rows[0]["pass_rate_value"], 100)
        self.assertFalse(level_rows[0]["below_target"])
        self.assertEqual(level_rows[1]["pass_rate_value"], 50)
        self.assertTrue(level_rows[1]["below_target"])
        self.assertEqual(level_chart_rows[0]["level"], "Year 1, Semester 1")
        self.assertEqual(level_chart_rows[0]["pass_rate"], "100%")
        self.assertEqual(level_chart_rows[0]["top_programme"], self.science_programme.name)
        self.assertEqual(level_chart_rows[0]["programme_breakdown"][0]["programme"], self.science_programme.name)
        self.assertEqual(level_chart_rows[0]["programme_breakdown"][0]["registrations"], 1)
        self.assertEqual(level_chart_rows[1]["level"], "Year 1, Semester 2")
        self.assertEqual(level_chart_rows[1]["pass_rate"], "50%")

        self.assertEqual(gender_rows[0]["label"], "Male")
        self.assertEqual(gender_rows[0]["pass_rate"], "100%")
        self.assertEqual(gender_rows[1]["label"], "Female")
        self.assertEqual(gender_rows[1]["pass_rate"], "50%")
        self.assertEqual(gender_rows[1]["average_mark"], 59)

        self.assertEqual(programme_rows[0]["programme"], self.science_programme.name)
        self.assertEqual(programme_rows[0]["pass_rate"], "100%")
        self.assertEqual(programme_rows[0]["level_breakdown"][0]["level"], "Year 1, Semester 1")
        self.assertEqual(programme_rows[0]["level_breakdown"][0]["registrations"], 1)
        self.assertEqual(programme_rows[1]["programme"], self.commerce_programme.name)
        self.assertEqual(programme_rows[1]["lead_level"], "Year 1, Semester 2")

    def test_academic_level_graph_breakdowns_follow_faculty_filter(self):
        """The academic-level deep-dive sections should respect active faculty filters."""

        response = self.client.get(
            reverse("dashboard:academic-level"),
            {"faculty": self.science_faculty.name},
        )

        level_rows = response.context["level_rows"]
        level_chart_rows = response.context["level_chart_rows"]
        gender_rows = response.context["gender_performance_rows"]
        programme_rows = response.context["programme_performance_rows"]

        self.assertEqual(len(level_rows), 1)
        self.assertEqual(level_chart_rows[0]["level"], "Year 1, Semester 1")
        self.assertEqual(level_chart_rows[0]["pass_rate"], "100%")
        self.assertEqual(level_chart_rows[0]["programme_breakdown"][0]["programme"], self.science_programme.name)
        self.assertEqual(gender_rows[0]["students"], 0)
        self.assertEqual(gender_rows[1]["students"], 1)
        self.assertEqual(gender_rows[1]["pass_rate"], "100%")
        self.assertEqual(len(programme_rows), 1)
        self.assertEqual(programme_rows[0]["programme"], self.science_programme.name)

    def test_academic_level_view_supplies_rule_based_card_narratives_by_default(self):
        """Academic-level cards should have deterministic narratives when AI insights are disabled."""

        response = self.client.get(reverse("dashboard:academic-level"))

        narratives = response.context["academic_level_card_narratives"]

        self.assertEqual(narratives["source"], "rules")
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
    def test_academic_level_view_uses_ai_card_narratives_when_available(self, mock_request):
        """Academic-level cards should prefer AI-written narratives when the Responses API succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"gender\\":{\\"insight\\":\\"AI gender insight\\",\\"action\\":\\"AI gender action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"top_enrolment\\":{\\"insight\\":\\"AI enrolment insight\\",\\"action\\":\\"AI enrolment action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"pass_trend\\":{\\"insight\\":\\"AI pass insight\\",\\"action\\":\\"AI pass action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:academic-level"))

        narratives = response.context["academic_level_card_narratives"]

        self.assertEqual(narratives["source"], "openai")
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
    def test_academic_level_view_can_use_google_card_narratives(self, mock_request):
        """Academic-level cards should support Gemini-generated narratives when Google is selected."""

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

        response = self.client.get(reverse("dashboard:academic-level"))

        narratives = response.context["academic_level_card_narratives"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(narratives["cards"]["gender"]["insight"], "Gemini gender insight")
        self.assertEqual(narratives["cards"]["top_enrolment"]["action"], "Gemini enrolment action")
        self.assertEqual(narratives["cards"]["pass_trend"]["insight"], "Gemini pass insight")
        self.assertEqual(narratives["cards"]["gender"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["gender"]["confidence"], "low")
        self.assertEqual(narratives["cards"]["top_enrolment"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["top_enrolment"]["confidence"], "low")
        self.assertEqual(narratives["cards"]["pass_trend"]["severity"], "high")
        self.assertEqual(narratives["cards"]["pass_trend"]["confidence"], "low")

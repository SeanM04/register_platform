"""Demographics feature tests."""

import urllib.error
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings
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
class DemographicViewTests(DashboardFixtureMixin, TestCase):
    """Exercise demographic analytics against the shared dashboard fixture."""

    def test_demographic_view_supplies_gender_location_and_programme_breakdowns(self):
        """Demographics page should expose grouped gender, location, and programme rows."""

        response = self.client.get(reverse("dashboard:demographic"))

        # Check that the shell renders correctly
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["summary_cards"]), 4)
        self.assertEqual(response.context["summary_cards"][0]["key"], "students")
        self.assertEqual(response.context["summary_cards"][0]["value"], "--")
        self.assertNotIn("gender_rows", response.context)
        self.assertNotIn("location_rows", response.context)
        self.assertNotIn("location_mix_rows", response.context)
        self.assertNotIn("location_map_rows", response.context)
        self.assertNotIn("location_map_meta", response.context)
        self.assertNotIn("programme_rows", response.context)
        self.assertNotIn("demographic_card_narratives", response.context)

    def test_demographic_payload_endpoint_supplies_data(self):
        """Demographic payload endpoint should return the heavy data for async loading."""

        response = self.client.get(reverse("dashboard:demographic-payload"))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        gender_rows = data["gender_rows"]
        location_rows = data["location_rows"]
        location_mix_rows = data["location_mix_rows"]
        location_map_rows = data["location_map_rows"]
        location_map_meta = data["location_map_meta"]
        metrics = data["metrics"]
        programme_rows = data["programme_rows"]

        self.assertEqual(metrics["students"], 2)
        self.assertEqual(metrics["male"], 1)
        self.assertEqual(metrics["female"], 1)
        self.assertEqual(metrics["birth_locations"], 2)

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

    def test_demographic_payload_endpoint_respects_faculty_filter(self):
        """Demographic payload should reflect the active faculty filter."""

        response = self.client.get(
            reverse("dashboard:demographic-payload"),
            {"faculty": self.science_faculty.name},
        )

        data = response.json()
        gender_rows = data["gender_rows"]
        location_rows = data["location_rows"]
        location_mix_rows = data["location_mix_rows"]
        location_map_rows = data["location_map_rows"]
        metrics = data["metrics"]
        programme_rows = data["programme_rows"]

        self.assertEqual(metrics["students"], 1)
        self.assertEqual(metrics["male"], 0)
        self.assertEqual(metrics["female"], 1)
        self.assertEqual(metrics["birth_locations"], 1)
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

    def test_demographic_metrics_endpoint_respects_visible_scope(self):
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

    def test_demographic_year_distribution_uses_cohort_timeline_under_topbar_filter(self):
        period_y1s1 = AcademicPeriod.objects.create(
            external_id=205001,
            academic_year="1",
            semester="1",
            name="2050 Jan - June",
        )
        period_y1s2 = AcademicPeriod.objects.create(
            external_id=205002,
            academic_year="1",
            semester="2",
            name="2050 July - December",
        )
        period_y2s1 = AcademicPeriod.objects.create(
            external_id=205101,
            academic_year="2",
            semester="1",
            name="2051 Jan - June",
        )

        intake_a = Student.objects.create(
            registration_number="REG101",
            first_names="Alice",
            surname="Moyo",
            gender="Female",
            place_of_birth="Harare",
        )
        intake_b = Student.objects.create(
            registration_number="REG102",
            first_names="Brian",
            surname="Dube",
            gender="Male",
            place_of_birth="Bulawayo",
        )
        intake_c = Student.objects.create(
            registration_number="REG103",
            first_names="Chipo",
            surname="Ncube",
            gender="Female",
            place_of_birth="Mutare",
        )

        registrations = [
            Registration.objects.create(
                external_id=50,
                student=intake_a,
                programme=self.science_programme,
                period=period_y1s1,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=51,
                student=intake_a,
                programme=self.science_programme,
                period=period_y1s2,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=52,
                student=intake_a,
                programme=self.science_programme,
                period=period_y2s1,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=53,
                student=intake_b,
                programme=self.science_programme,
                period=period_y1s2,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=54,
                student=intake_b,
                programme=self.science_programme,
                period=period_y2s1,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=55,
                student=intake_c,
                programme=self.science_programme,
                period=period_y2s1,
                decision="proceed",
                carrying=0,
            ),
        ]
        for registration, mark in zip(registrations, [78, 75, 72, 69, 74, 81]):
            CourseResult.objects.create(registration=registration, course=self.course, mark=mark)

        response = self.client.get(
            reverse("dashboard:demographic-payload"),
            {"year": "2051", "period": "Jan - June"},
        )

        data = response.json()
        year_rows = {row["year"]: row for row in data["year_distribution_rows"]}

        self.assertEqual(year_rows["1"]["total"], 2)
        self.assertEqual(year_rows["1"]["male"], 1)
        self.assertEqual(year_rows["1"]["female"], 1)
        self.assertEqual(year_rows["2"]["total"], 1)
        self.assertEqual(year_rows["2"]["male"], 0)
        self.assertEqual(year_rows["2"]["female"], 1)

    def test_demographic_narratives_endpoint_supplies_rule_based_narratives(self):
        """Demographics narratives endpoint should expose deterministic narratives when AI is off."""

        response = self.client.get(reverse("dashboard:demographic-narratives"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "rules")
        self.assertEqual(diagnostics["returned_source"], "rules")
        self.assertEqual(diagnostics["status"], "rules")
        self.assertEqual(diagnostics["fallback_reason"], "provider_rules_configured")
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

    @override_settings(
        AI_INSIGHTS_ENABLED=True,
        AI_INSIGHTS_PROVIDER="openai",
        OPENAI_INSIGHTS_ENABLED=True,
        OPENAI_API_KEY="test-key",
    )
    @patch("dashboard.demographics.ai_insights._request_demographic_openai_narratives")
    def test_demographic_narratives_endpoint_uses_ai_when_available(self, mock_request):
        """Demographics narratives endpoint should prefer OpenAI copy when the provider succeeds."""

        mock_request.return_value = """
        {
            "output_text": "{\\"cards\\":{\\"gender\\":{\\"insight\\":\\"AI gender insight\\",\\"action\\":\\"AI gender action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"medium\\"},\\"location\\":{\\"insight\\":\\"AI location insight\\",\\"action\\":\\"AI location action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"location_mix\\":{\\"insight\\":\\"AI location mix insight\\",\\"action\\":\\"AI location mix action\\",\\"severity\\":\\"medium\\",\\"confidence\\":\\"medium\\"},\\"programme\\":{\\"insight\\":\\"AI programme insight\\",\\"action\\":\\"AI programme action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"high\\"},\\"origin_map\\":{\\"insight\\":\\"AI map insight\\",\\"action\\":\\"AI map action\\",\\"severity\\":\\"stable\\",\\"confidence\\":\\"high\\"}}}"
        }
        """

        response = self.client.get(reverse("dashboard:demographic-narratives"))

        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "openai")
        self.assertEqual(diagnostics["returned_source"], "openai")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "openai")
        self.assertEqual(narratives["cards"]["gender"]["insight"], "AI gender insight")
        self.assertEqual(narratives["cards"]["location"]["action"], "AI location action")
        self.assertEqual(narratives["cards"]["location_mix"]["insight"], "AI location mix insight")
        self.assertEqual(narratives["cards"]["programme"]["action"], "AI programme action")
        self.assertEqual(narratives["cards"]["origin_map"]["insight"], "AI map insight")
        self.assertEqual(narratives["cards"]["location"]["severity"], "medium")
        self.assertEqual(narratives["cards"]["programme"]["confidence"], "high")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.demographics.ai_insights._request_demographic_google_narratives")
    def test_demographic_narratives_endpoint_can_use_google(self, mock_request):
        """Demographics narratives endpoint should support Gemini-generated narratives."""

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

        response = self.client.get(reverse("dashboard:demographic-narratives"))

        payload = response.json()
        narratives = payload["card_narratives"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(narratives["source"], "google")
        self.assertEqual(diagnostics["returned_source"], "google")
        self.assertEqual(diagnostics["status"], "ai")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(narratives["cards"]["gender"]["insight"], "Gemini gender insight")
        self.assertEqual(narratives["cards"]["location"]["action"], "Gemini location action")
        self.assertEqual(narratives["cards"]["location_mix"]["insight"], "Gemini location mix insight")
        self.assertEqual(narratives["cards"]["programme"]["action"], "Gemini programme action")
        self.assertEqual(narratives["cards"]["origin_map"]["insight"], "Gemini map insight")
        self.assertEqual(narratives["cards"]["gender"]["severity"], "stable")
        self.assertEqual(narratives["cards"]["gender"]["confidence"], "low")

    @override_settings(AI_INSIGHTS_ENABLED=True, AI_INSIGHTS_PROVIDER="google", GOOGLE_API_KEY="test-google-key")
    @patch("dashboard.demographics.ai_insights._request_demographic_google_narratives")
    def test_demographic_narratives_endpoint_reports_structured_fallback_diagnostics_when_google_fails(self, mock_request):
        """Demographic narratives should expose a stable fallback reason when Gemini cannot be reached."""

        mock_request.side_effect = OSError("WinError 10013 network blocked")

        response = self.client.get(reverse("dashboard:demographic-narratives"))

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
    @patch("dashboard.demographics.ai_insights._request_demographic_google_narratives")
    def test_demographic_narratives_endpoint_reports_rate_limit_diagnostics_for_google_429(self, mock_request):
        """Demographic narratives should explain when Gemini rejects the request with a quota/rate-limit response."""

        mock_request.side_effect = urllib.error.HTTPError(
            "https://example.com",
            429,
            "Too Many Requests",
            None,
            None,
        )

        response = self.client.get(reverse("dashboard:demographic-narratives"))

        diagnostics = response.json()["diagnostics"]

        self.assertEqual(diagnostics["status"], "fallback")
        self.assertEqual(diagnostics["provider_attempted"], "google")
        self.assertEqual(diagnostics["fallback_reason"], "google_rate_limited")
        self.assertIn("quota or request limits", diagnostics["message"])

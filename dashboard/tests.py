"""Dashboard view tests covering filters, summaries, and navigation state."""

import csv
import shutil
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import UserType

from .models import (
    AcademicDecision,
    AcademicPeriod,
    AttendanceType,
    Cohort,
    CompletionAnalysisRecord,
    Registration,
    CourseResult,
    Student,
    ZeroCompletionReason,
)
from .test_support import DashboardFixtureMixin


@override_settings(
    AI_INSIGHTS_ENABLED=False,
    OPENAI_INSIGHTS_ENABLED=False,
    AI_INSIGHTS_PROVIDER="rules",
    GOOGLE_API_KEY="",
    OPENAI_API_KEY="",
)
class DashboardViewTests(DashboardFixtureMixin, TestCase):
    """Exercise the production-facing dashboard views against real query patterns."""

    def test_dashboard_home_metrics_endpoint_respects_year_filter(self):
        """Home metrics JSON should follow the selected topbar filters."""

        response = self.client.get(reverse("dashboard:home-metrics"), {"year": "2026"})

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["enrolled"], 1)
        self.assertEqual(metrics["registered"], 1)
        self.assertEqual(metrics["pass_rate"], "100%")
        self.assertEqual(metrics["on_time_graduation"], 1)

    def test_programme_metrics_endpoint_respects_faculty_filter(self):
        """Programme metrics JSON should respect the selected faculty."""

        response = self.client.get(
            reverse("dashboard:programme-metrics"),
            {"faculty": self.science_faculty.name},
        )

        metrics = response.json()["metrics"]
        self.assertEqual(metrics["programmes"], 1)
        self.assertEqual(metrics["registrations"], 1)
        self.assertEqual(metrics["students"], 1)
        self.assertEqual(metrics["average_pass_rate"], "100%")

    def test_insights_view_renders_lightweight_shell(self):
        """Insights page should render the shared shell and defer heavy payloads."""

        response = self.client.get(reverse("dashboard:insights"))

        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(active_labels, ["Insights"])
        self.assertEqual(len(response.context["summary_cards"]), 4)
        self.assertTrue(all(card["value"] == "--" for card in response.context["summary_cards"]))
        self.assertContains(response, reverse("dashboard:insights-payload"))

    def test_layout_context_exposes_chatbot_bootstrap(self):
        """Shared dashboard context should expose chatbot config to the base template."""

        response = self.client.get(reverse("dashboard:insights"))

        chatbot_bootstrap = response.context["chatbot_bootstrap"]
        self.assertEqual(response.status_code, 200)
        self.assertTrue(chatbot_bootstrap["enabled"])
        self.assertEqual(chatbot_bootstrap["page_key"], "insights")
        self.assertEqual(chatbot_bootstrap["endpoint"], reverse("chatbot:message"))
        self.assertTrue(chatbot_bootstrap["suggestions"])

    def test_student_list_shows_each_student_once_with_latest_registration_details(self):
        """Students page should collapse multiple registrations into one latest row per student."""

        response = self.client.get(reverse("dashboard:students"))

        students = response.context["students"]
        alice_rows = [row for row in students if row["name"] == self.student_primary.full_name]
        self.assertEqual(len(alice_rows), 1)
        self.assertEqual(alice_rows[0]["program"], self.science_programme.name)
        self.assertEqual(alice_rows[0]["department"], self.science_department.name)
        self.assertEqual(alice_rows[0]["decision"], "Proceed")

    def test_student_list_search_preserves_matching_registration_context(self):
        """Students search should keep the latest registration inside the matched subset."""

        response = self.client.get(reverse("dashboard:students"), {"q": "Accounting"})

        students = response.context["students"]
        alice_rows = [row for row in students if row["name"] == self.student_primary.full_name]
        self.assertEqual(len(alice_rows), 1)
        self.assertEqual(alice_rows[0]["program"], self.commerce_programme.name)
        self.assertEqual(alice_rows[0]["department"], self.commerce_department.name)
        self.assertEqual(alice_rows[0]["decision"], "Pending")

    def test_student_detail_back_link_preserves_unfiltered_students_list(self):
        """Back from student detail should return to the original students list filter state."""

        students_response = self.client.get(reverse("dashboard:students"))
        student_link = next(
            row for row in students_response.context["students"]
            if row["name"] == self.student_primary.full_name
        )
        detail_response = self.client.get(
            reverse("dashboard:student-detail", args=[student_link["detail_slug"]]),
            {"return_to": reverse("dashboard:students")},
        )

        self.assertEqual(detail_response.context["back_to_students_url"], reverse("dashboard:students"))
        self.assertNotContains(detail_response, "href=\"/students?faculty=")

    def test_student_detail_scopes_topbar_filters_to_student_records(self):
        """Student detail filters should expose only years, periods, and faculties the student has."""

        response = self.client.get(
            reverse("dashboard:student-detail", args=[self.student_primary.registration_number.lower()]),
            {"year": "2099", "period": "Missing", "faculty": "ENGINEERING"},
        )

        filters = {row["name"]: row for row in response.context["filters"]}
        self.assertEqual(filters["faculty"]["options"], [self.commerce_faculty.name, self.science_faculty.name])
        self.assertFalse(filters["faculty"]["disabled"])
        self.assertNotIn("ENGINEERING", filters["faculty"]["options"])
        self.assertEqual(response.context["selected_faculty"], self.science_faculty.name)
        self.assertEqual(response.context["selected_year"], "Year 1")
        self.assertEqual(response.context["selected_period"], "Jan - June")
        self.assertContains(response, "Foundations of Computing")

    def test_student_detail_locks_faculty_filter_for_single_faculty_student(self):
        """A student with one faculty should have a single locked faculty option."""

        response = self.client.get(
            reverse("dashboard:student-detail", args=[self.student_secondary.registration_number.lower()]),
            {"faculty": self.science_faculty.name},
        )

        filters = {row["name"]: row for row in response.context["filters"]}
        self.assertEqual(filters["faculty"]["options"], [self.commerce_faculty.name])
        self.assertTrue(filters["faculty"]["disabled"])
        self.assertEqual(response.context["selected_faculty"], self.commerce_faculty.name)

    def test_student_detail_keeps_database_years_visible_without_course_rows(self):
        """Student year tabs should reflect stored registrations even before course rows exist."""

        empty_period = AcademicPeriod.objects.create(
            external_id=202701,
            academic_year="2",
            semester="1",
            name="2027 January - June",
        )
        Registration.objects.create(
            external_id=99,
            student=self.student_primary,
            programme=self.science_programme,
            period=empty_period,
            decision="pending",
            carrying=0,
        )

        response = self.client.get(
            reverse("dashboard:student-detail", args=[self.student_primary.registration_number.lower()]),
        )

        filters = {row["name"]: row for row in response.context["filters"]}
        year_tabs = response.context["student"]["year_dropdown_tabs"]
        visible_tab_years = [row["year"] for row in year_tabs]
        self.assertEqual(filters["year"]["options"], ["Year 1"])
        self.assertEqual(visible_tab_years, [1])
        self.assertEqual(len(year_tabs[0]["semesters"]), 2)
        self.assertContains(response, "2027 January - June")

    def test_student_detail_rebases_non_contiguous_imported_years_for_display(self):
        """Student detail should show contiguous study years even when imported period years jump."""

        year2_period = AcademicPeriod.objects.create(
            external_id=202701,
            academic_year="2",
            semester="1",
            name="2027 January - June",
        )
        year2_sem2_period = AcademicPeriod.objects.create(
            external_id=202702,
            academic_year="2",
            semester="2",
            name="2027 August - December",
        )
        year3_period = AcademicPeriod.objects.create(
            external_id=202801,
            academic_year="3",
            semester="1",
            name="2028 January - June",
        )
        year5_period = AcademicPeriod.objects.create(
            external_id=202901,
            academic_year="5",
            semester="1",
            name="2029 January - June",
        )
        student = Student.objects.create(
            registration_number="REG003",
            first_names="Chipo",
            surname="Dube",
            gender="Female",
            place_of_birth="Mutare",
        )
        registrations = [
            Registration.objects.create(
                external_id=30,
                student=student,
                programme=self.science_programme,
                period=year2_period,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=31,
                student=student,
                programme=self.science_programme,
                period=year2_sem2_period,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=32,
                student=student,
                programme=self.science_programme,
                period=year3_period,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=33,
                student=student,
                programme=self.science_programme,
                period=year5_period,
                decision="proceed",
                carrying=0,
            ),
        ]
        for index, registration in enumerate(registrations, start=1):
            CourseResult.objects.create(
                registration=registration,
                course=self.course,
                mark=60 + index,
            )

        response = self.client.get(
            reverse("dashboard:student-detail", args=[student.registration_number.lower()]),
        )

        filters = {row["name"]: row for row in response.context["filters"]}
        visible_tab_years = [row["year"] for row in response.context["student"]["year_dropdown_tabs"]]
        self.assertEqual(filters["year"]["options"], ["Year 2", "Year 1"])
        self.assertEqual(visible_tab_years, [2, 1])
        self.assertContains(response, "Year 1")
        self.assertContains(response, "Year 2")

    def test_student_detail_orders_latest_year_left_and_latest_semester_first(self):
        """Student year dropdowns should show newest years first and semester 2 above semester 1."""

        year2_period = AcademicPeriod.objects.create(
            external_id=202701,
            academic_year="2",
            semester="1",
            name="2027 January - June",
        )
        year2_sem2_period = AcademicPeriod.objects.create(
            external_id=202702,
            academic_year="2",
            semester="2",
            name="2027 August - December",
        )
        student = Student.objects.create(
            registration_number="REG005",
            first_names="Nyasha",
            surname="Zhou",
            gender="Female",
            place_of_birth="Kwekwe",
        )
        registrations = [
            Registration.objects.create(
                external_id=50,
                student=student,
                programme=self.science_programme,
                period=self.period_2025,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=51,
                student=student,
                programme=self.science_programme,
                period=self.period_2026,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=52,
                student=student,
                programme=self.science_programme,
                period=year2_period,
                decision="proceed",
                carrying=0,
            ),
            Registration.objects.create(
                external_id=53,
                student=student,
                programme=self.science_programme,
                period=year2_sem2_period,
                decision="proceed",
                carrying=0,
            ),
        ]
        for index, registration in enumerate(registrations, start=1):
            CourseResult.objects.create(
                registration=registration,
                course=self.course,
                mark=69 + index,
            )

        response = self.client.get(
            reverse("dashboard:student-detail", args=[student.registration_number.lower()]),
            {"term": "2:2", "year": "Year 2"},
        )

        year_tabs = response.context["student"]["year_dropdown_tabs"]
        self.assertEqual([tab["year"] for tab in year_tabs], [2, 1])
        self.assertEqual(year_tabs[0]["semesters"][0]["label"], "Semester 2")
        self.assertEqual(year_tabs[0]["semesters"][1]["label"], "Semester 1")
        self.assertEqual(year_tabs[0]["display_label"], "Year 2 Semester 2")

    def test_student_detail_rebases_initial_semester_two_to_semester_one_display(self):
        """A student's first visible semester should not start at semester two in the UI."""

        student = Student.objects.create(
            registration_number="REG004",
            first_names="Tariro",
            surname="Sibanda",
            gender="Female",
            place_of_birth="Gweru",
        )
        registration = Registration.objects.create(
            external_id=40,
            student=student,
            programme=self.science_programme,
            period=self.period_2025,
            decision="proceed",
            carrying=0,
        )
        CourseResult.objects.create(
            registration=registration,
            course=self.course,
            mark=67,
        )

        response = self.client.get(
            reverse("dashboard:student-detail", args=[student.registration_number.lower()]),
        )

        self.assertEqual(response.context["student"]["academic_level"], "Year 1 Semester 1")
        year_tabs = response.context["student"]["year_dropdown_tabs"]
        self.assertEqual(len(year_tabs), 1)
        self.assertEqual(year_tabs[0]["year_label"], "Year 1")
        self.assertEqual(year_tabs[0]["semesters"][0]["label"], "Semester 1")

    def test_student_detail_collapses_repeated_semesters_into_one_tab(self):
        """Repeated registrations in the same official year/semester should not create extra tabs."""

        repeat_period = AcademicPeriod.objects.create(
            external_id=202701,
            academic_year="1",
            semester="1",
            name="2026 January - June Repeat",
        )
        repeat_registration = Registration.objects.create(
            external_id=77,
            student=self.student_primary,
            programme=self.science_programme,
            period=repeat_period,
            decision="repeat",
            carrying=1,
        )
        CourseResult.objects.create(
            registration=repeat_registration,
            course=self.course,
            mark=65,
            attendance_type="Repeat",
        )

        response = self.client.get(
            reverse("dashboard:student-detail", args=[self.student_primary.registration_number.lower()]),
            {"faculty": self.science_faculty.name},
        )

        year_tabs = response.context["student"]["year_dropdown_tabs"]
        self.assertEqual(len(year_tabs), 1)
        self.assertEqual(year_tabs[0]["year"], 1)
        self.assertEqual(len(year_tabs[0]["semesters"]), 1)

    def test_student_detail_splits_repeated_semester_results_by_period(self):
        """Repeated semester results should show the latest period first and earlier attempts below it."""

        repeat_period = AcademicPeriod.objects.create(
            external_id=202203,
            academic_year="1",
            semester="1",
            name="May 2022 - August 2022",
        )
        latest_period = AcademicPeriod.objects.create(
            external_id=202206,
            academic_year="1",
            semester="1",
            name="September 2022 - December 2022",
        )
        first_registration = Registration.objects.create(
            external_id=80,
            student=self.student_secondary,
            programme=self.commerce_programme,
            period=repeat_period,
            decision="repeat",
            carrying=1,
        )
        latest_registration = Registration.objects.create(
            external_id=81,
            student=self.student_secondary,
            programme=self.commerce_programme,
            period=latest_period,
            decision="proceed carrying",
            carrying=1,
        )
        CourseResult.objects.create(
            registration=first_registration,
            course=self.course,
            mark=48,
        )
        CourseResult.objects.create(
            registration=latest_registration,
            course=self.course,
            mark=62,
            attendance_type="Repeat",
        )

        response = self.client.get(
            reverse("dashboard:student-detail", args=[self.student_secondary.registration_number.lower()]),
            {
                "faculty": self.commerce_faculty.name,
                "term": "1:1",
                "year": "Year 1",
                "period": "September - December",
            },
        )

        self.assertEqual(response.context["student"]["term_name"], "September 2022 - December 2022")
        result_sections = response.context["student"]["result_sections"]
        self.assertEqual(
            [section["period_name"] for section in result_sections],
            ["September 2022 - December 2022", "May 2022 - August 2022"],
        )

    def test_student_detail_promotes_new_module_set_out_of_repeated_semester_bucket(self):
        """A later same-stage registration with new modules should become the next displayed semester."""

        first_period = AcademicPeriod.objects.create(
            external_id=202101,
            academic_year="1",
            semester="1",
            name="September 2021 - December 2021",
        )
        repeat_period = AcademicPeriod.objects.create(
            external_id=202203,
            academic_year="1",
            semester="1",
            name="May 2022 - August 2022",
        )
        new_set_period = AcademicPeriod.objects.create(
            external_id=202206,
            academic_year="1",
            semester="1",
            name="September 2022 - December 2022",
        )
        follow_up_period = AcademicPeriod.objects.create(
            external_id=202301,
            academic_year="1",
            semester="2",
            name="March 2023 - July 2023",
        )
        course_a = self.course
        from .models import Course
        course_b = Course.objects.create(code="ASTA101", name="Introduction to Statistics")
        course_c = Course.objects.create(code="ACCT123", name="Financial Accounting for Business Ib")
        course_d = Course.objects.create(code="BMAN121", name="Commercial Law")
        course_e = Course.objects.create(code="SSHR211", name="HR Practice")

        student = Student.objects.create(
            registration_number="REG006",
            first_names="Blake",
            surname="Allen",
            gender="Female",
            place_of_birth="Mutare",
        )
        first_registration = Registration.objects.create(
            external_id=90,
            student=student,
            programme=self.science_programme,
            period=first_period,
            decision="repeat",
            carrying=1,
        )
        repeat_registration = Registration.objects.create(
            external_id=91,
            student=student,
            programme=self.science_programme,
            period=repeat_period,
            decision="repeat",
            carrying=1,
        )
        new_set_registration = Registration.objects.create(
            external_id=92,
            student=student,
            programme=self.science_programme,
            period=new_set_period,
            decision="proceed carrying",
            carrying=1,
        )
        follow_up_registration = Registration.objects.create(
            external_id=93,
            student=student,
            programme=self.science_programme,
            period=follow_up_period,
            decision="proceed",
            carrying=0,
        )

        CourseResult.objects.create(registration=first_registration, course=course_a, mark=35)
        CourseResult.objects.create(registration=first_registration, course=course_b, mark=27)
        CourseResult.objects.create(registration=repeat_registration, course=course_a, mark=50, attendance_type="Repeat")
        CourseResult.objects.create(registration=repeat_registration, course=course_b, mark=55, attendance_type="Repeat")
        CourseResult.objects.create(registration=new_set_registration, course=course_c, mark=41)
        CourseResult.objects.create(registration=new_set_registration, course=course_d, mark=34)
        CourseResult.objects.create(registration=follow_up_registration, course=course_c, mark=52, attendance_type="Carry")
        CourseResult.objects.create(registration=follow_up_registration, course=course_e, mark=60)

        response = self.client.get(
            reverse("dashboard:student-detail", args=[student.registration_number.lower()]),
            {"term": "1:2", "year": "Year 1", "period": "September - December"},
        )

        self.assertEqual(response.context["student"]["academic_level"], "Year 1 Semester 2")
        sections = response.context["student"]["result_sections"]
        self.assertEqual([section["period_name"] for section in sections], ["September 2022 - December 2022"])
        year_tabs = response.context["student"]["year_dropdown_tabs"]
        self.assertEqual(year_tabs[-1]["year_label"], "Year 1")
        self.assertEqual([option["label"] for option in year_tabs[-1]["semesters"]], ["Semester 2", "Semester 1"])

    def test_student_transcript_keeps_retakes_in_their_actual_semester(self):
        """Transcript rows should preserve attempt history without creating fake years."""

        failed_period = AcademicPeriod.objects.create(
            external_id=202401,
            academic_year="1",
            semester="1",
            name="2024 January - June",
        )
        carry_period = AcademicPeriod.objects.create(
            external_id=202801,
            academic_year="2",
            semester="1",
            name="2025 January - June",
        )
        failed_registration = Registration.objects.create(
            external_id=88,
            student=self.student_secondary,
            programme=self.commerce_programme,
            period=failed_period,
            decision="fail",
            carrying=1,
        )
        carried_registration = Registration.objects.create(
            external_id=89,
            student=self.student_secondary,
            programme=self.commerce_programme,
            period=carry_period,
            decision="proceed",
            carrying=0,
        )
        CourseResult.objects.create(
            registration=failed_registration,
            course=self.course,
            mark=42,
        )
        CourseResult.objects.create(
            registration=carried_registration,
            course=self.course,
            mark=68,
            attendance_type="Repeat",
        )

        response = self.client.get(
            reverse("dashboard:student-transcript", args=[self.student_secondary.registration_number.lower()]),
        )

        transcript_results = response.context["transcript_results"]
        year_semester_pairs = [(row["academic_year"], row["period"]) for row in transcript_results if row["course_code"] == self.course.code]
        self.assertIn(("Year 1", "Semester 1"), year_semester_pairs)
        self.assertIn(("Year 2", "Semester 1"), year_semester_pairs)
        self.assertTrue(any("Attempt 2" in row["course_display_name"] for row in transcript_results))

    @override_settings(
        CHATBOT_ENABLED=True,
        CHATBOT_PROVIDER="google",
        GOOGLE_API_KEY="test-google-key",
    )
    @patch("services.chatbot_service._request_google_chatbot_response")
    def test_chatbot_message_endpoint_returns_google_reply(self, mock_request):
        """The chatbot endpoint should return provider-generated copy when AI succeeds."""

        mock_request.return_value = (
            '{"candidates":[{"content":{"parts":[{"text":"AI summary for the current scope."}]}}]}'
        )

        response = self.client.post(
            reverse("chatbot:message"),
            data={
                "message": "Summarize the current scope.",
                "filters": {"year": "2026", "faculty": self.science_faculty.name},
                "history": [{"role": "user", "content": "Hello"}],
            },
            content_type="application/json",
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["source"], "google")
        self.assertEqual(payload["reply"], "AI summary for the current scope.")
        self.assertEqual(payload["diagnostics"]["returned_source"], "google")

    def test_student_list_paginates_in_the_database(self):
        """Students page should fetch only the requested page instead of materializing the full directory."""

        for index in range(3, 28):
            student = Student.objects.create(
                registration_number=f"REG{index:03d}",
                first_names=f"Student{index}",
                surname="LoadTest",
                gender="Female",
                place_of_birth="Windhoek",
            )
            Registration.objects.create(
                external_id=100 + index,
                student=student,
                programme=self.science_programme,
                period=self.period_2026,
                decision="proceed",
                carrying=0,
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("dashboard:students"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["students"]), 7)
        student_queries = [
            query["sql"]
            for query in queries.captured_queries
            if 'FROM "dashboard_student"' in query["sql"]
        ]
        self.assertTrue(student_queries)
        self.assertTrue(any("OFFSET 20" in query.upper() for query in student_queries))

    def test_programme_view_respects_faculty_filter(self):
        """Programme payload should only include rows from the selected faculty."""

        response = self.client.get(
            reverse("dashboard:programme-payload"),
            {"faculty": self.science_faculty.name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        programme_rows = response.json()["programme_rows"]
        self.assertEqual(len(programme_rows), 1)
        self.assertEqual(programme_rows[0]["faculty"], self.science_faculty.name)
        self.assertEqual(programme_rows[0]["name"], self.science_programme.name)

    def test_sidebar_marks_current_section_active(self):
        """The current section should be the only active sidebar item."""

        response = self.client.get(reverse("dashboard:demographic"))

        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]
        self.assertEqual(active_labels, ["Demographics"])

    def test_admin_can_access_system_management(self):
        """Platform admins should see & access the system management workspace."""

        response = self.client.get(reverse("dashboard:system-management"))

        self.assertEqual(response.status_code, 200)
        active_labels = [item["label"] for item in response.context["sidebar_items"] if item["is_active"]]
        self.assertEqual(active_labels, ["System Management"])

    def test_non_admin_cannot_access_system_management(self):
        """Non-admin users should be blocked from the system management page."""

        viewer_role = UserType.objects.create(code="viewer", name="Viewer")
        non_admin = get_user_model().objects.create_user(
            email="viewer@example.com",
            password="StrongPass123!",
            first_name="Viewer",
            last_name="User",
            user_type=viewer_role,
            is_active=True,
        )
        self.client.force_login(non_admin)

        response = self.client.get(reverse("dashboard:system-management"))

        self.assertEqual(response.status_code, 403)

    def test_system_management_can_create_user(self):
        """System management POST should provision a new user through the custom form."""

        response = self.client.post(
            reverse("dashboard:system-management"),
            {
                "action": "create-user",
                "first_name": "System",
                "last_name": "Operator",
                "email": "operator@example.com",
                "user_type": self.user_type.id,
                "is_active": "on",
                "grant_staff_access": "on",
                "password1": "OperatorPass123!",
                "password2": "OperatorPass123!",
                "next": reverse("dashboard:system-management"),
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = get_user_model().objects.get(email="operator@example.com")
        self.assertEqual(created_user.first_name, "System")
        self.assertTrue(created_user.is_active)
        self.assertTrue(created_user.is_staff)
        self.assertEqual(created_user.user_type, self.user_type)


class RegistrarImportCommandTests(TestCase):
    """Verify the registrar import command decomposes CSVs into relational tables."""

    def _write_csv(self, directory, filename, headers, rows):
        path = Path(directory) / filename
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_import_command_loads_completion_export_and_calculates_age(self):
        temp_root = Path.cwd() / "data" / ".test_import_command"
        temp_dir = temp_root / "case_one"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        registrations_csv = self._write_csv(
            temp_dir,
            "Registrations.csv",
            [
                "id",
                "regnum",
                "firstnames",
                "surname",
                "programme_id",
                "programme_code",
                "programme_name",
                "faculty",
                "department",
                "dob",
                "gender",
                "place_of_birth",
                "psid",
                "attendance_type_id",
                "registration_id",
                "period_id",
                "academic_year",
                "semester",
                "period_name",
                "decision",
                "carrying",
            ],
            [
                {
                    "id": "1",
                    "regnum": "REG100",
                    "firstnames": "Ada",
                    "surname": "Moyo",
                    "programme_id": "10",
                    "programme_code": "BSC-STAT",
                    "programme_name": "Bachelor of Science in Statistics",
                    "faculty": "Science",
                    "department": "Mathematics",
                    "dob": "2000-01-10",
                    "gender": "Female",
                    "place_of_birth": "Harare",
                    "psid": "501",
                    "attendance_type_id": "1",
                    "registration_id": "9001",
                    "period_id": "202601",
                    "academic_year": "1",
                    "semester": "1",
                    "period_name": "2026 January - June",
                    "decision": "Pending",
                    "carrying": "0",
                }
            ],
        )
        marks_csv = self._write_csv(
            temp_dir,
            "course final marks by period.csv",
            [
                "code",
                "name",
                "period_name",
                "period_id",
                "regnum",
                "programme_code",
                "programme_name",
                "attendance_type",
                "mark",
                "gradingrule",
            ],
            [
                {
                    "code": "STA101",
                    "name": "Statistics I",
                    "period_name": "2026 January - June",
                    "period_id": "202601",
                    "regnum": "REG100",
                    "programme_code": "BSC-STAT",
                    "programme_name": "Bachelor of Science in Statistics",
                    "attendance_type": "Conventional",
                    "mark": "78",
                    "gradingrule": "100-50~P#49-0~F",
                }
            ],
        )
        completion_csv = self._write_csv(
            temp_dir,
            "completion_analysis.csv",
            [
                "Registration Number",
                "Student Name",
                "Programme",
                "Academic Stage",
                "Decision",
                "Effective Cohort",
                "Original Cohort",
                "Shifted",
                "Zero Completion Reason",
                "Completion Rate",
            ],
            [
                {
                    "Registration Number": "REG100",
                    "Student Name": "Ada Moyo",
                    "Programme": "Bachelor of Science in Statistics",
                    "Academic Stage": "Year 1, Semester 1",
                    "Decision": "Pending",
                    "Effective Cohort": "JANUARY 2026 - JUNE 2026",
                    "Original Cohort": "JANUARY 2026 - JUNE 2026",
                    "Shifted": "No",
                    "Zero Completion Reason": "",
                    "Completion Rate": "78%",
                }
            ],
        )

        call_command(
            "import_registrar_data",
            str(registrations_csv),
            str(marks_csv),
            str(completion_csv),
        )

        student = Student.objects.get(registration_number="REG100")
        registration = Registration.objects.get()
        self.assertEqual(student.age, student.current_age)
        self.assertEqual(registration.source_row_id, 1)
        self.assertEqual(registration.student_internal_id, 501)
        self.assertEqual(registration.attendance_type_record.name, "Conventional")
        self.assertEqual(registration.decision_record.label, "Pending")
        self.assertTrue(AttendanceType.objects.filter(name="Conventional").exists())
        self.assertTrue(AcademicDecision.objects.filter(label="Pending").exists())

        completion_row = CompletionAnalysisRecord.objects.get()
        self.assertEqual(completion_row.student.registration_number, "REG100")
        self.assertEqual(completion_row.programme.code, "BSC-STAT")
        self.assertEqual(completion_row.academic_year, "1")
        self.assertEqual(completion_row.semester, "1")
        self.assertEqual(str(completion_row.completion_rate), "78.00")
        self.assertFalse(completion_row.shifted)
        self.assertTrue(Cohort.objects.filter(name="JANUARY 2026 - JUNE 2026").exists())
        self.assertEqual(ZeroCompletionReason.objects.count(), 0)

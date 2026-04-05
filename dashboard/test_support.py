"""Shared dashboard test fixtures."""

from django.contrib.auth import get_user_model

from accounts.models import UserType

from .models import AcademicPeriod, Course, CourseResult, Department, Faculty, Programme, Registration, Student


class DashboardFixtureMixin:
    """Build a small but realistic academic dataset for dashboard feature tests."""

    def setUp(self):
        super().setUp()
        self.user_type, _ = UserType.objects.get_or_create(
            code="admin",
            defaults={"name": "Admin"},
        )
        self.user = get_user_model().objects.create_user(
            email="owner@example.com",
            password="StrongPass123!",
            first_name="Owner",
            last_name="User",
            user_type=self.user_type,
            is_active=True,
        )
        self.client.force_login(self.user)

        self.science_faculty = Faculty.objects.create(name="Science Faculty")
        self.commerce_faculty = Faculty.objects.create(name="Commerce Faculty")
        self.science_department = Department.objects.create(
            faculty=self.science_faculty,
            name="Department of Computing",
        )
        self.commerce_department = Department.objects.create(
            faculty=self.commerce_faculty,
            name="Department of Accounting",
        )
        self.science_programme = Programme.objects.create(
            department=self.science_department,
            external_id=101,
            code="BSC-INF",
            name="BSc Informatics",
        )
        self.commerce_programme = Programme.objects.create(
            department=self.commerce_department,
            external_id=102,
            code="BCOM-ACC",
            name="BCom Accounting",
        )
        self.period_2026 = AcademicPeriod.objects.create(
            external_id=202601,
            academic_year="1",
            semester="1",
            name="2026 Jan - June",
        )
        self.period_2025 = AcademicPeriod.objects.create(
            external_id=202501,
            academic_year="1",
            semester="2",
            name="2025 July - December",
        )
        self.course = Course.objects.create(code="CSC101", name="Foundations of Computing")

        self.student_primary = Student.objects.create(
            registration_number="REG001",
            first_names="Alice",
            surname="Ncube",
            gender="Female",
            place_of_birth="Bulawayo",
        )
        self.student_secondary = Student.objects.create(
            registration_number="REG002",
            first_names="Brian",
            surname="Moyo",
            gender="Male",
            place_of_birth="Harare",
        )

        self.primary_old_registration = Registration.objects.create(
            external_id=1,
            student=self.student_primary,
            programme=self.commerce_programme,
            period=self.period_2025,
            decision="pending",
            carrying=1,
        )
        self.primary_latest_registration = Registration.objects.create(
            external_id=2,
            student=self.student_primary,
            programme=self.science_programme,
            period=self.period_2026,
            decision="proceed",
            carrying=0,
        )
        self.secondary_registration = Registration.objects.create(
            external_id=3,
            student=self.student_secondary,
            programme=self.commerce_programme,
            period=self.period_2025,
            decision="retake",
            carrying=1,
        )

        CourseResult.objects.create(
            registration=self.primary_old_registration,
            course=self.course,
            mark=40,
        )
        CourseResult.objects.create(
            registration=self.primary_latest_registration,
            course=self.course,
            mark=78,
        )
        CourseResult.objects.create(
            registration=self.secondary_registration,
            course=self.course,
            mark=55,
        )

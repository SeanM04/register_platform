import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dashboard.models import (
    AcademicPeriod,
    Course,
    CourseResult,
    Department,
    Faculty,
    Programme,
    Registration,
    Student,
)


def parse_date(value):
    """Convert CSV date string into a ``date`` object (supports multiple formats)."""

    if not value:
        return None

    value = value.strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Unsupported date format: {value}")


def parse_decimal(value):
    """Safely convert a CSV mark value into ``Decimal`` or return ``None``."""

    if value in (None, ""):
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    """Import registrar registration and marks CSV data into dashboard models."""

    help = "Import registration and course result data from the registrar CSV files."

    def add_arguments(self, parser):
        """Register the two required CSV file path arguments for the command."""

        parser.add_argument("registrations_csv", type=str)
        parser.add_argument("marks_csv", type=str)

    @transaction.atomic
    def handle(self, *args, **options):
        """Clear existing academic data and rebuild it from the provided CSV files."""

        registrations_path = Path(options["registrations_csv"])
        marks_path = Path(options["marks_csv"])

        if not registrations_path.exists():
            raise CommandError(f"Registrations CSV not found: {registrations_path}")
        if not marks_path.exists():
            raise CommandError(f"Marks CSV not found: {marks_path}")

        self.stdout.write("Clearing existing imported academic data...")
        CourseResult.objects.all().delete()
        Registration.objects.all().delete()
        Course.objects.all().delete()
        Student.objects.all().delete()
        AcademicPeriod.objects.all().delete()
        Programme.objects.all().delete()
        Department.objects.all().delete()
        Faculty.objects.all().delete()

        self.stdout.write("Importing registrations...")
        registration_index = {}

        with registrations_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                faculty, _ = Faculty.objects.get_or_create(name=row["faculty"].strip())
                department, _ = Department.objects.get_or_create(
                    faculty=faculty,
                    name=row["department"].strip(),
                )
                programme, _ = Programme.objects.get_or_create(
                    code=row["programme_code"].strip(),
                    defaults={
                        "department": department,
                        "external_id": int(row["programme_id"]) if row["programme_id"] else None,
                        "name": row["programme_name"].strip(),
                    },
                )
                if programme.department_id != department.id:
                    programme.department = department
                    programme.save(update_fields=["department", "updated_at"])

                period, _ = AcademicPeriod.objects.get_or_create(
                    external_id=int(row["period_id"]),
                    defaults={
                        "academic_year": row["academic_year"].strip(),
                        "semester": row["semester"].strip(),
                        "name": row["period_name"].strip(),
                    },
                )

                student, _ = Student.objects.get_or_create(
                    registration_number=row["regnum"].strip(),
                    defaults={
                        "first_names": row["firstnames"].strip(),
                        "surname": row["surname"].strip(),
                        "date_of_birth": parse_date(row["dob"].strip()) if row["dob"] else None,
                        "gender": row["gender"].strip(),
                        "place_of_birth": row["place_of_birth"].strip(),
                    },
                )

                registration = Registration.objects.create(
                    external_id=int(row["registration_id"]),
                    student=student,
                    programme=programme,
                    period=period,
                    student_internal_id=int(row["psid"]) if row["psid"] else None,
                    attendance_type_id=int(row["attendance_type_id"]) if row["attendance_type_id"] else None,
                    decision=row["decision"].strip(),
                    carrying=int(row["carrying"]) if row["carrying"] else 0,
                )
                registration_index[(student.registration_number, period.external_id)] = registration

        self.stdout.write("Importing course results...")

        with marks_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                registration = registration_index.get((row["regnum"].strip(), int(row["period_id"])))
                if not registration:
                    continue

                course, _ = Course.objects.get_or_create(
                    code=row["code"].strip(),
                    defaults={"name": row["name"].strip()},
                )
                if course.name != row["name"].strip():
                    course.name = row["name"].strip()
                    course.save(update_fields=["name", "updated_at"])

                CourseResult.objects.update_or_create(
                    registration=registration,
                    course=course,
                    defaults={
                        "attendance_type": row["attendance_type"].strip(),
                        "mark": parse_decimal(row["mark"].strip()),
                        "grading_rule": row["gradingrule"].strip(),
                    },
                )

        self.stdout.write(self.style.SUCCESS("Registrar CSV import completed successfully."))

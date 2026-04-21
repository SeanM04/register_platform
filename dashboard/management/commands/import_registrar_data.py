import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from dashboard.models import (
    AcademicDecision,
    AcademicPeriod,
    AttendanceType,
    Cohort,
    CompletionAnalysisRecord,
    Course,
    CourseResult,
    Department,
    Faculty,
    Programme,
    Registration,
    Student,
    ZeroCompletionReason,
)


def parse_date(value):
    """Convert CSV date string into a ``date`` object (supports multiple formats)."""

    if not value:
        return None

    value = value.strip()

    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def parse_decimal(value):
    """Safely convert a CSV mark value into ``Decimal`` or return ``None``."""

    if value in (None, ""):
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def calculate_age(date_of_birth, today=None):
    """Return whole-year age from a date of birth."""

    if not date_of_birth:
        return None

    today = today or timezone.localdate()
    age = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def parse_boolish(value):
    """Convert free-text yes/no style values into booleans."""

    normalized = str(value or "").strip().lower()
    return normalized in {"yes", "y", "true", "1", "shifted"}


def parse_percentage_decimal(value):
    """Convert a display value like ``78%`` into a ``Decimal``."""

    normalized = str(value or "").strip().replace("%", "")
    return parse_decimal(normalized)


def normalize_key(value):
    """Normalize free-text dimension values into stable lookup keys."""

    return " ".join(str(value or "").strip().lower().split())


def normalize_name_match(value):
    """Normalize institution labels for cross-file name matching."""

    normalized = str(value or "").strip().lower().replace("&", " and ")
    for token in [",", ".", "-", "/", "(", ")"]:
        normalized = normalized.replace(token, " ")
    return " ".join(normalized.split())


def parse_academic_stage(stage):
    """Extract academic year and semester from labels like ``Year 4, Semester 1``."""

    normalized = str(stage or "").strip()
    if not normalized:
        return "", ""

    year = ""
    semester = ""
    lowered = normalized.lower().replace(",", " ")
    tokens = lowered.split()
    for index, token in enumerate(tokens):
        if token == "year" and index + 1 < len(tokens):
            year = tokens[index + 1]
        if token == "semester" and index + 1 < len(tokens):
            semester = tokens[index + 1]
    return year, semester


def get_decision(label):
    """Return the normalized academic decision dimension row."""

    normalized = normalize_key(label)
    if not normalized:
        return None
    decision, _ = AcademicDecision.objects.get_or_create(
        normalized_key=normalized,
        defaults={"label": str(label or "").strip()},
    )
    if decision.label != str(label or "").strip():
        decision.label = str(label or "").strip()
        decision.save(update_fields=["label", "updated_at"])
    return decision


def get_attendance_type(external_id=None, name=""):
    """Return the attendance type dimension row from either ID or name input."""

    clean_name = str(name or "").strip()
    if external_id is not None:
        normalized = f"id:{external_id}"
        attendance_type, _ = AttendanceType.objects.get_or_create(
            normalized_key=normalized,
            defaults={
                "external_id": external_id,
                "name": clean_name or f"Attendance Type {external_id}",
            },
        )
        if clean_name and attendance_type.name != clean_name:
            attendance_type.name = clean_name
            attendance_type.save(update_fields=["name", "updated_at"])
        return attendance_type

    if not clean_name:
        return None
    attendance_type, _ = AttendanceType.objects.get_or_create(
        normalized_key=f"name:{normalize_key(clean_name)}",
        defaults={"name": clean_name},
    )
    return attendance_type


def get_cohort(name, sort_index):
    """Return a cohort dimension row for completion effective/original cohorts."""

    clean_name = str(name or "").strip()
    if not clean_name:
        return None
    cohort, _ = Cohort.objects.get_or_create(
        name=clean_name,
        defaults={"sort_index": sort_index},
    )
    if sort_index and cohort.sort_index != sort_index:
        cohort.sort_index = sort_index
        cohort.save(update_fields=["sort_index", "updated_at"])
    return cohort


def get_zero_completion_reason(label):
    """Return the zero-completion reason dimension row when present."""

    clean_label = str(label or "").strip()
    if not clean_label:
        return None
    reason, _ = ZeroCompletionReason.objects.get_or_create(label=clean_label)
    return reason


class Command(BaseCommand):
    """Import registrar registration and marks CSV data into dashboard models."""

    help = "Import registration and course result data from the registrar CSV files."

    def add_arguments(self, parser):
        """Register the two required CSV file path arguments for the command."""

        parser.add_argument("registrations_csv", type=str)
        parser.add_argument("marks_csv", type=str)
        parser.add_argument("completion_analysis_csv", type=str, nargs="?")

    @transaction.atomic
    def handle(self, *args, **options):
        """Clear existing academic data and rebuild it from the provided CSV files."""

        registrations_path = Path(options["registrations_csv"])
        marks_path = Path(options["marks_csv"])
        completion_analysis_path = Path(options["completion_analysis_csv"]) if options.get("completion_analysis_csv") else None

        if not registrations_path.exists():
            raise CommandError(f"Registrations CSV not found: {registrations_path}")
        if not marks_path.exists():
            raise CommandError(f"Marks CSV not found: {marks_path}")
        if completion_analysis_path and not completion_analysis_path.exists():
            raise CommandError(f"Completion analysis CSV not found: {completion_analysis_path}")

        self.stdout.write("Clearing existing imported academic data...")
        CompletionAnalysisRecord.objects.all().delete()
        CourseResult.objects.all().delete()
        Registration.objects.all().delete()
        Course.objects.all().delete()
        Student.objects.all().delete()
        AcademicPeriod.objects.all().delete()
        Programme.objects.all().delete()
        Department.objects.all().delete()
        Faculty.objects.all().delete()
        ZeroCompletionReason.objects.all().delete()
        Cohort.objects.all().delete()
        AcademicDecision.objects.all().delete()
        AttendanceType.objects.all().delete()

        self.stdout.write("Importing registrations...")
        registration_index = {}
        student_index = {}
        programme_name_index = {}
        today = timezone.localdate()

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
                if row["programme_id"] and programme.external_id != int(row["programme_id"]):
                    programme.external_id = int(row["programme_id"])
                if programme.name != row["programme_name"].strip():
                    programme.name = row["programme_name"].strip()
                programme.save()
                programme_name_index[normalize_name_match(programme.name)] = programme
                period, _ = AcademicPeriod.objects.get_or_create(
                    external_id=int(row["period_id"]),
                    defaults={
                        "academic_year": row["academic_year"].strip(),
                        "semester": row["semester"].strip(),
                        "name": row["period_name"].strip(),
                    },
                )
                updated_period_fields = []
                if period.academic_year != row["academic_year"].strip():
                    period.academic_year = row["academic_year"].strip()
                    updated_period_fields.append("academic_year")
                if period.semester != row["semester"].strip():
                    period.semester = row["semester"].strip()
                    updated_period_fields.append("semester")
                if period.name != row["period_name"].strip():
                    period.name = row["period_name"].strip()
                    updated_period_fields.append("name")
                if updated_period_fields:
                    updated_period_fields.append("updated_at")
                    period.save(update_fields=updated_period_fields)

                date_of_birth = parse_date(row["dob"].strip()) if row["dob"] else None
                age = calculate_age(date_of_birth, today=today)
                student, _ = Student.objects.get_or_create(
                    registration_number=row["regnum"].strip(),
                    defaults={
<<<<<<< HEAD
                        "first_names": row.get("firstnames", row["regnum"]).strip() if row.get("firstnames") else row["regnum"].strip(),
                        "surname": row.get("surname", "").strip() if row.get("surname") else "",
                        "date_of_birth": parse_date(row["dob"].strip()) if row.get("dob") else None,
                        "gender": row.get("gender", "").strip() if row.get("gender") else "",
                        "place_of_birth": row.get("place_of_birth", "").strip() if row.get("place_of_birth") else "",
=======
                        "first_names": row["firstnames"].strip(),
                        "surname": row["surname"].strip(),
                        "date_of_birth": date_of_birth,
                        "age": age,
                        "gender": row["gender"].strip(),
                        "place_of_birth": row["place_of_birth"].strip(),
>>>>>>> 0b29128a186194f720af652f8db96a4b6fbfce7b
                    },
                )
                updated_student_fields = []
                if student.first_names != row["firstnames"].strip():
                    student.first_names = row["firstnames"].strip()
                    updated_student_fields.append("first_names")
                if student.surname != row["surname"].strip():
                    student.surname = row["surname"].strip()
                    updated_student_fields.append("surname")
                if student.date_of_birth != date_of_birth:
                    student.date_of_birth = date_of_birth
                    updated_student_fields.append("date_of_birth")
                if student.age != age:
                    student.age = age
                    updated_student_fields.append("age")
                if student.gender != row["gender"].strip():
                    student.gender = row["gender"].strip()
                    updated_student_fields.append("gender")
                if student.place_of_birth != row["place_of_birth"].strip():
                    student.place_of_birth = row["place_of_birth"].strip()
                    updated_student_fields.append("place_of_birth")
                if updated_student_fields:
                    updated_student_fields.append("updated_at")
                    student.save(update_fields=updated_student_fields)
                student_index[student.registration_number] = student

                registration = Registration.objects.create(
                    source_row_id=int(row["id"]) if row["id"] else None,
                    external_id=int(row["registration_id"]),
                    student=student,
                    programme=programme,
                    period=period,
                    student_internal_id=int(row["psid"]) if row["psid"] else None,
                    attendance_type_id=int(row["attendance_type_id"]) if row["attendance_type_id"] else None,
                    decision=row["decision"].strip(),
                    attendance_type_record=get_attendance_type(
                        external_id=int(row["attendance_type_id"]) if row["attendance_type_id"] else None,
                    ),
                    decision_record=get_decision(row["decision"].strip()),
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

                attendance_type = get_attendance_type(name=row["attendance_type"].strip())
                CourseResult.objects.update_or_create(
                    registration=registration,
                    course=course,
                    defaults={
                        "attendance_type": row["attendance_type"].strip(),
                        "attendance_type_record": attendance_type,
                        "mark": parse_decimal(row["mark"].strip()),
                        "grading_rule": row["gradingrule"].strip(),
                    },
                )

                if attendance_type and registration.attendance_type_id and registration.attendance_type_record != attendance_type:
                    registration.attendance_type_record = attendance_type
                    registration.save(update_fields=["attendance_type_record", "updated_at"])

        if completion_analysis_path:
            self.stdout.write("Importing completion analysis export...")
            cohort_sort_indexes = {}
            with completion_analysis_path.open(newline="", encoding="utf-8-sig") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    registration_number = row["Registration Number"].strip()
                    student = student_index.get(registration_number)
                    programme = None
                    programme_name = row["Programme"].strip()
                    if student and programme_name:
                        programme = programme_name_index.get(normalize_name_match(programme_name))
                    if not programme and programme_name:
                        programme = programme_name_index.get(normalize_name_match(programme_name))

                    if not student or not programme:
                        continue

                    effective_cohort_name = row["Effective Cohort"].strip()
                    original_cohort_name = row["Original Cohort"].strip()
                    for cohort_name in [original_cohort_name, effective_cohort_name]:
                        if cohort_name and cohort_name not in cohort_sort_indexes:
                            cohort_sort_indexes[cohort_name] = len(cohort_sort_indexes) + 1

                    academic_year, semester = parse_academic_stage(row["Academic Stage"])
                    CompletionAnalysisRecord.objects.update_or_create(
                        student=student,
                        programme=programme,
                        academic_stage=row["Academic Stage"].strip(),
                        effective_cohort=get_cohort(
                            effective_cohort_name,
                            cohort_sort_indexes.get(effective_cohort_name, 0),
                        ),
                        defaults={
                            "academic_year": academic_year,
                            "semester": semester,
                            "decision": get_decision(row["Decision"].strip()),
                            "original_cohort": get_cohort(
                                original_cohort_name,
                                cohort_sort_indexes.get(original_cohort_name, 0),
                            ),
                            "shifted": parse_boolish(row["Shifted"]),
                            "zero_completion_reason": get_zero_completion_reason(row["Zero Completion Reason"]),
                            "completion_rate": parse_percentage_decimal(row["Completion Rate"]),
                        },
                    )
        else:
            self.stdout.write(self.style.WARNING("No completion analysis CSV supplied; skipping completion export import."))

        self.stdout.write(self.style.SUCCESS("Registrar CSV import completed successfully."))

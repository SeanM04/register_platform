from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Programme(TimeStampedModel):
    department = models.ForeignKey("Department", on_delete=models.PROTECT, related_name="programmes", null=True, blank=True)
    external_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def faculty(self):
        return self.department.faculty

    @property
    def normalized_name(self):
        """Return programme name with Bsc & Bcom corrected to BSc & BCom, & And/and replaced with &."""
        if not self.name:
            return self.name
        # Replace Bsc with BSc & Bcom with BCom (case-sensitive)
        normalized = self.name.replace("Bsc", "BSc")
        normalized = normalized.replace("Bcom", "BCom")
        # Replace coordinating conjunctions with & symbol
        normalized = normalized.replace(" AND ", " & ")
        normalized = normalized.replace(" And ", " & ")
        normalized = normalized.replace(" and ", " & ")
        return normalized


class Faculty(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "faculties"

    def __str__(self):
        return self.name


class Department(TimeStampedModel):
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="departments")
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["name"]
        unique_together = [("faculty", "name")]

    def __str__(self):
        return self.name


class AcademicPeriod(TimeStampedModel):
    external_id = models.PositiveIntegerField(unique=True)
    academic_year = models.CharField(max_length=20, blank=True)
    semester = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Student(TimeStampedModel):
    registration_number = models.CharField(max_length=30, unique=True)
    first_names = models.CharField(max_length=255)
    surname = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    place_of_birth = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["surname", "first_names"]

    def __str__(self):
        return f"{self.first_names} {self.surname}".strip()

    @property
    def full_name(self):
        return f"{self.first_names} {self.surname}".strip()

    @property
    def current_age(self):
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        years = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years


class AttendanceType(TimeStampedModel):
    external_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=100)
    normalized_key = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicDecision(TimeStampedModel):
    label = models.CharField(max_length=100)
    normalized_key = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return self.label


class Cohort(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    sort_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_index", "name"]

    def __str__(self):
        return self.name


class ZeroCompletionReason(TimeStampedModel):
    label = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return self.label


class Registration(TimeStampedModel):
    source_row_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    external_id = models.PositiveIntegerField(unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="registrations")
    programme = models.ForeignKey(Programme, on_delete=models.PROTECT, related_name="registrations")
    period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT, related_name="registrations")
    student_internal_id = models.PositiveIntegerField(null=True, blank=True)
    attendance_type_id = models.PositiveIntegerField(null=True, blank=True)
    decision = models.CharField(max_length=100, blank=True)
    attendance_type_record = models.ForeignKey(AttendanceType, on_delete=models.SET_NULL, related_name="registrations", null=True, blank=True)
    decision_record = models.ForeignKey(AcademicDecision, on_delete=models.SET_NULL, related_name="registrations", null=True, blank=True)
    carrying = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["student__surname", "student__first_names"]
        unique_together = [("student", "period", "programme")]

    def __str__(self):
        return f"{self.student} - {self.period}"


class CourseResult(TimeStampedModel):
    course = models.ForeignKey("Course", on_delete=models.PROTECT, related_name="results", null=True, blank=True)
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name="course_results")
    attendance_type = models.CharField(max_length=100, blank=True)
    attendance_type_record = models.ForeignKey(AttendanceType, on_delete=models.SET_NULL, related_name="course_results", null=True, blank=True)
    mark = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grading_rule = models.TextField(blank=True)

    class Meta:
        ordering = ["course__code"]
        unique_together = [("registration", "course")]

    def __str__(self):
        return f"{self.course.code} - {self.registration.student}"


class Course(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class CompletionAnalysisRecord(TimeStampedModel):
    student = models.ForeignKey("Student", on_delete=models.CASCADE, related_name="completion_analysis_records")
    programme = models.ForeignKey("Programme", on_delete=models.PROTECT, related_name="completion_analysis_records")
    academic_stage = models.CharField(max_length=100, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    semester = models.CharField(max_length=20, blank=True)
    decision = models.ForeignKey(AcademicDecision, on_delete=models.SET_NULL, related_name="completion_analysis_records", null=True, blank=True)
    effective_cohort = models.ForeignKey(Cohort, on_delete=models.SET_NULL, related_name="effective_completion_records", null=True, blank=True)
    original_cohort = models.ForeignKey(Cohort, on_delete=models.SET_NULL, related_name="original_completion_records", null=True, blank=True)
    shifted = models.BooleanField(default=False)
    zero_completion_reason = models.ForeignKey(ZeroCompletionReason, on_delete=models.SET_NULL, related_name="completion_analysis_records", null=True, blank=True)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["programme__name", "student__registration_number"]
        unique_together = [("student", "programme", "academic_stage", "effective_cohort")]

    def __str__(self):
        return f"{self.student.registration_number} - {self.programme.name}"

from django.db import models


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
        """Return programme name with Bsc corrected to BSc."""
        if not self.name:
            return self.name
        # Replace Bsc with BSc (case-sensitive)
        return self.name.replace("Bsc", "BSc")


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
    gender = models.CharField(max_length=20, blank=True)
    place_of_birth = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["surname", "first_names"]

    def __str__(self):
        return f"{self.first_names} {self.surname}".strip()

    @property
    def full_name(self):
        return f"{self.first_names} {self.surname}".strip()


class Registration(TimeStampedModel):
    external_id = models.PositiveIntegerField(unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="registrations")
    programme = models.ForeignKey(Programme, on_delete=models.PROTECT, related_name="registrations")
    period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT, related_name="registrations")
    student_internal_id = models.PositiveIntegerField(null=True, blank=True)
    attendance_type_id = models.PositiveIntegerField(null=True, blank=True)
    decision = models.CharField(max_length=100, blank=True)
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

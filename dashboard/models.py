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

    @property
    def age_with_details(self):
        """Return age with detailed breakdown (years, months, days)."""
        if not self.date_of_birth:
            return None
        
        today = timezone.localdate()
        birth_date = self.date_of_birth
        
        # Calculate years
        years = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            years -= 1
        
        # Calculate months
        months = today.month - birth_date.month
        if months < 0:
            months += 12
            years -= 1
        
        # Calculate days
        days = today.day - birth_date.day
        if days < 0:
            # Get days in previous month
            import calendar
            if today.month == 1:
                prev_month = 12
                prev_year = today.year - 1
            else:
                prev_month = today.month - 1
                prev_year = today.year
            
            days_in_prev_month = calendar.monthrange(prev_year, prev_month)[1]
            days += days_in_prev_month
            months -= 1
            if months < 0:
                months += 12
                years -= 1
        
        return {
            'years': years,
            'months': months,
            'days': days,
            'formatted': f"{years} years, {months} months, {days} days"
        }

    @property
    def age_category(self):
        """Categorize student by age for demographic analysis."""
        age = self.current_age
        if age is None:
            return "Unknown"
        elif age < 18:
            return "Under 18"
        elif age < 20:
            return "18-19"
        elif age < 22:
            return "20-21"
        elif age < 25:
            return "22-24"
        elif age < 30:
            return "25-29"
        else:
            return "30+"


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


_SENSITIVE_POST_FIELDS = frozenset({
    "password", "password1", "password2", "token", "secret",
    "key", "api_key", "access_token", "refresh_token", "csrfmiddlewaretoken",
})


def _get_client_ip(request):
    try:
        from ipware import get_client_ip

        ip, _ = get_client_ip(request)
        return ip
    except ImportError:
        return request.META.get("REMOTE_ADDR", "")


class AuditLog(models.Model):
    ACTION_USER_CREATED = "user_created"
    ACTION_USER_ACTIVATED = "user_activated"
    ACTION_USER_DEACTIVATED = "user_deactivated"
    ACTION_LOCKOUT_CLEARED = "lockout_cleared"
    ACTION_AI_PROVIDER_CHANGED = "ai_provider_changed"
    ACTION_LOGIN_SUCCESS = "login_success"
    ACTION_LOGIN_FAILED = "login_failed"
    ACTION_LOGOUT = "logout"

    ACTION_CHOICES = [
        (ACTION_USER_CREATED, "User created"),
        (ACTION_USER_ACTIVATED, "User activated"),
        (ACTION_USER_DEACTIVATED, "User deactivated"),
        (ACTION_LOCKOUT_CLEARED, "Lockout cleared"),
        (ACTION_AI_PROVIDER_CHANGED, "AI provider changed"),
        (ACTION_LOGIN_SUCCESS, "Login"),
        (ACTION_LOGIN_FAILED, "Login failed"),
        (ACTION_LOGOUT, "Logout"),
    ]

    ACTION_TONE = {
        ACTION_USER_CREATED: "success",
        ACTION_USER_ACTIVATED: "success",
        ACTION_USER_DEACTIVATED: "warning",
        ACTION_LOCKOUT_CLEARED: "info",
        ACTION_AI_PROVIDER_CHANGED: "info",
        ACTION_LOGIN_SUCCESS: "neutral",
        ACTION_LOGIN_FAILED: "danger",
        ACTION_LOGOUT: "neutral",
    }

    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
    )
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    target_email = models.EmailField(blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["actor_email"]),
        ]

    @classmethod
    def record(cls, action, *, actor=None, target_email="", detail=None, request=None):
        ip = None
        if request is not None:
            ip = _get_client_ip(request)
            if actor is None and hasattr(request, "user") and request.user.is_authenticated:
                actor = request.user
        actor_email = actor.email if actor is not None else ""
        cls.objects.create(
            actor=actor,
            actor_email=actor_email,
            action=action,
            target_email=target_email,
            detail=detail or {},
            ip_address=ip,
        )


class ErrorLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="error_logs",
    )
    user_email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    exception_type = models.CharField(max_length=200, db_index=True)
    exception_message = models.TextField(blank=True)
    traceback = models.TextField(blank=True)
    get_params = models.JSONField(default=dict, blank=True)
    post_params = models.JSONField(default=dict, blank=True)
    resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_errors",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = "error_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["exception_type"]),
            models.Index(fields=["resolved", "-timestamp"]),
        ]

    def __str__(self):
        status = "resolved" if self.resolved else "open"
        return f"{self.exception_type} at {self.path} [{status}]"

    @classmethod
    def from_request(cls, request, exception, tb_str=""):
        user = None
        user_email = ""
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
            user_email = request.user.email

        get_params = dict(request.GET.lists())
        post_params = {
            k: ["[REDACTED]"] if k.lower() in _SENSITIVE_POST_FIELDS else list(v)
            for k, v in request.POST.lists()
        }

        cls.objects.create(
            path=request.path[:500],
            method=request.method,
            user=user,
            user_email=user_email,
            ip_address=_get_client_ip(request),
            exception_type=type(exception).__name__[:200],
            exception_message=str(exception)[:2000],
            traceback=tb_str,
            get_params=get_params,
            post_params=post_params,
        )


class PlatformSetting(models.Model):
    """Runtime-configurable key/value store for platform-wide settings."""

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, default="")

    class Meta:
        db_table = "platform_settings"

    def __str__(self):
        return f"{self.key}={self.value!r}"

    @classmethod
    def get_value(cls, key, default=""):
        try:
            return cls.objects.values_list("value", flat=True).get(key=key)
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_value(cls, key, value):
        cls.objects.update_or_create(key=key, defaults={"value": str(value)})

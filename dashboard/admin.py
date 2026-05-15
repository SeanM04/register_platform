from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    AcademicDecision,
    AcademicPeriod,
    AttendanceType,
    Cohort,
    CompletionAnalysisRecord,
    Course,
    CourseResult,
    Department,
    ErrorLog,
    Faculty,
    Programme,
    Registration,
    Student,
    ZeroCompletionReason,
)


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty")
    list_filter = ("faculty",)
    search_fields = ("name", "faculty__name")


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "faculty")
    list_filter = ("department__faculty", "department")
    search_fields = ("code", "name", "department__name", "department__faculty__name")


@admin.register(AcademicPeriod)
class AcademicPeriodAdmin(admin.ModelAdmin):
    list_display = ("external_id", "name", "academic_year", "semester")
    search_fields = ("name",)


@admin.register(AttendanceType)
class AttendanceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "external_id", "normalized_key")
    search_fields = ("name", "normalized_key")


@admin.register(AcademicDecision)
class AcademicDecisionAdmin(admin.ModelAdmin):
    list_display = ("label", "normalized_key")
    search_fields = ("label", "normalized_key")


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_index")
    search_fields = ("name",)


@admin.register(ZeroCompletionReason)
class ZeroCompletionReasonAdmin(admin.ModelAdmin):
    list_display = ("label",)
    search_fields = ("label",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "first_names", "surname", "age", "gender", "place_of_birth")
    search_fields = ("registration_number", "first_names", "surname")


class CourseResultInline(admin.TabularInline):
    model = CourseResult
    extra = 0


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "programme", "period", "decision", "attendance_type_record", "carrying", "source_row_id")
    list_filter = ("decision_record", "attendance_type_record", "programme", "period")
    search_fields = ("student__registration_number", "student__first_names", "student__surname")
    inlines = [CourseResultInline]


@admin.register(CourseResult)
class CourseResultAdmin(admin.ModelAdmin):
    list_display = ("course", "registration", "attendance_type_record", "mark")
    list_filter = ("attendance_type_record", "registration__period", "registration__programme")
    search_fields = ("course__code", "course__name", "registration__student__registration_number")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(CompletionAnalysisRecord)
class CompletionAnalysisRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "programme", "academic_stage", "decision", "completion_rate")
    list_filter = ("effective_cohort", "original_cohort", "shifted", "decision")
    search_fields = (
        "student__registration_number",
        "student__first_names",
        "student__surname",
        "programme__name",
    )


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    list_per_page = 25

    list_display = (
        "timestamp",
        "exception_type",
        "path",
        "method",
        "user_email",
        "status_badge",
    )
    list_filter = ("resolved", "method", "exception_type")
    search_fields = ("path", "exception_type", "exception_message", "user_email")

    readonly_fields = (
        "timestamp",
        "path",
        "method",
        "user",
        "user_email",
        "ip_address",
        "exception_type",
        "exception_message",
        "traceback_display",
        "get_params",
        "post_params",
        "resolved_at",
        "resolved_by",
    )

    fieldsets = (
        ("Request", {
            "fields": ("timestamp", "path", "method", "user", "user_email", "ip_address"),
        }),
        ("Exception", {
            "fields": ("exception_type", "exception_message", "traceback_display"),
        }),
        ("Request Data", {
            "fields": ("get_params", "post_params"),
            "classes": ("collapse",),
        }),
        ("Resolution", {
            "fields": ("resolved", "resolved_by", "resolved_at", "resolution_notes"),
        }),
    )

    actions = ["mark_resolved", "mark_unresolved"]

    # ── Custom columns ──────────────────────────────────────────

    @admin.display(description="Status", ordering="resolved", boolean=False)
    def status_badge(self, obj):
        if obj.resolved:
            return format_html(
                '<span style="color:#166534;font-weight:700;">&#10003; Resolved</span>'
            )
        return format_html(
            '<span style="color:#be123c;font-weight:700;">&#10007; Open</span>'
        )

    @admin.display(description="Traceback")
    def traceback_display(self, obj):
        if not obj.traceback:
            return "—"
        return format_html(
            '<pre style="white-space:pre-wrap;font-size:11px;'
            'max-height:400px;overflow:auto;background:#f8f9fa;'
            'padding:0.75rem;border-radius:6px">{}</pre>',
            obj.traceback,
        )

    # ── Save hook ───────────────────────────────────────────────

    def save_model(self, request, obj, form, change):
        if obj.resolved and not obj.resolved_at:
            obj.resolved_at = timezone.now()
            obj.resolved_by = request.user
        elif not obj.resolved:
            obj.resolved_at = None
            obj.resolved_by = None
        super().save_model(request, obj, form, change)

    # ── Bulk actions ────────────────────────────────────────────

    @admin.action(description="Mark selected errors as resolved")
    def mark_resolved(self, request, queryset):
        updated = queryset.filter(resolved=False).update(
            resolved=True,
            resolved_by=request.user,
            resolved_at=timezone.now(),
        )
        self.message_user(request, f"{updated} error(s) marked as resolved.")

    @admin.action(description="Reopen selected errors")
    def mark_unresolved(self, request, queryset):
        updated = queryset.filter(resolved=True).update(
            resolved=False,
            resolved_by=None,
            resolved_at=None,
        )
        self.message_user(request, f"{updated} error(s) reopened.")

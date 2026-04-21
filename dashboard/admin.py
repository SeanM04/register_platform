from django.contrib import admin
from .models import (
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
    search_fields = ("student__registration_number", "student__first_names", "student__surname", "programme__name")

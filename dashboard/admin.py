from django.contrib import admin
from .models import (
    AcademicPeriod,
    Course,
    CourseResult,
    Department,
    Faculty,
    Programme,
    Registration,
    Student,
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


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "first_names", "surname", "gender", "place_of_birth")
    search_fields = ("registration_number", "first_names", "surname")


class CourseResultInline(admin.TabularInline):
    model = CourseResult
    extra = 0


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "programme", "period", "decision", "carrying")
    list_filter = ("decision", "programme", "period")
    search_fields = ("student__registration_number", "student__first_names", "student__surname")
    inlines = [CourseResultInline]


@admin.register(CourseResult)
class CourseResultAdmin(admin.ModelAdmin):
    list_display = ("course", "registration", "mark")
    list_filter = ("registration__period", "registration__programme")
    search_fields = ("course__code", "course__name", "registration__student__registration_number")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

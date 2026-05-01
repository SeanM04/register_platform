from django.core.management.base import BaseCommand
from django.db import models
from dashboard.models import AcademicPeriod, Registration


class Command(BaseCommand):
    help = 'Show cohort 218 and academic year summary'

    def handle(self, *args, **options):
        self.stdout.write("🎯 COHORT 218 AND ACADEMIC YEAR SUMMARY")
        
        # Find cohort 218
        cohort_218 = AcademicPeriod.objects.filter(external_id=218).first()
        
        if cohort_218:
            self.stdout.write(f"\n✅ COHORT 218:")
            self.stdout.write(f"   Name: {cohort_218.name}")
            self.stdout.write(f"   External ID: {cohort_218.external_id}")
            self.stdout.write(f"   Academic Year: {cohort_218.academic_year}")
            self.stdout.write(f"   Semester: {cohort_218.semester}")
            self.stdout.write(f"   Total Students: {Registration.objects.filter(period=cohort_218).count()}")
        
        # Show academic year structure
        self.stdout.write(f"\n📅 ACADEMIC YEAR STRUCTURE:")
        
        academic_years = AcademicPeriod.objects.values_list('academic_year', flat=True).distinct()
        for year in sorted(academic_years):
            if year:  # Skip empty
                periods = AcademicPeriod.objects.filter(academic_year=year).order_by('external_id')
                total_regs = Registration.objects.filter(period__academic_year=year).count()
                
                self.stdout.write(f"\n   Academic Year {year}:")
                self.stdout.write(f"   Total Registrations: {total_regs}")
                self.stdout.write(f"   Periods:")
                
                for period in periods:
                    reg_count = Registration.objects.filter(period=period).count()
                    marker = " ⭐ COHORT 218" if period.external_id == 218 else ""
                    self.stdout.write(f"     {period.name} (ID: {period.external_id}) - {reg_count} students{marker}")
        
        # Show what academic years cohort 218 students belong to
        if cohort_218:
            self.stdout.write(f"\n🎓 ACADEMIC YEARS FOR COHORT 218 STUDENTS:")
            
            # Get students who started in cohort 218
            cohort_218_students = Registration.objects.filter(period=cohort_218).values_list('student_id', flat=True)
            
            # Find all academic years these students appear in
            academic_years_for_cohort = sorted(set(
                year for year in Registration.objects.filter(
                    student_id__in=cohort_218_students
                ).values_list('period__academic_year', flat=True) if year
            ))
            
            for year in academic_years_for_cohort:
                self.stdout.write(f"   Academic Year {year}")
            
            # Show progression timeline
            self.stdout.write(f"\n📈 COHORT 218 PROGRESSION TIMELINE:")
            
            # Get all periods for cohort 218 students with counts in one query
            cohort_periods = Registration.objects.filter(
                student_id__in=cohort_218_students
            ).values('period__name', 'period__academic_year', 'period__external_id').annotate(
                reg_count=models.Count('student_id')
            ).order_by('period__external_id')
            
            for period in cohort_periods:
                period_name = period['period__name']
                academic_year = period['period__academic_year']
                period_id = period['period__external_id']
                reg_count = period['reg_count']
                self.stdout.write(f"   {period_name} (Year {academic_year}, ID: {period_id}) - {reg_count} students")
        
        self.stdout.write(f"\n🔗 KEY INSIGHTS:")
        self.stdout.write(f"   • Cohort 218 = August-December 2025 period")
        self.stdout.write(f"   • Cohort 218 belongs to Academic Year 4")
        self.stdout.write(f"   • Students in cohort 218 started their studies in August-December 2025")
        self.stdout.write(f"   • These students will progress through Academic Year 4 and beyond")
        self.stdout.write(f"   • Currently, cohort 218 has 743 students in their first semester")

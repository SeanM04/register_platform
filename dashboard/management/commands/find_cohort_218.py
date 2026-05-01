from django.core.management.base import BaseCommand
from django.db import models
from dashboard.models import AcademicPeriod, Registration


class Command(BaseCommand):
    help = 'Find academic years in cohort 218 and August-December 2025'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Finding cohort 218 and August-December 2025 information...")
        
        # Find cohort 218
        cohort_218 = AcademicPeriod.objects.filter(external_id=218).first()
        
        if cohort_218:
            self.stdout.write(f"\n🎯 COHORT 218 FOUND:")
            self.stdout.write(f"  Name: {cohort_218.name}")
            self.stdout.write(f"  External ID: {cohort_218.external_id}")
            self.stdout.write(f"  Academic Year: {cohort_218.academic_year}")
            self.stdout.write(f"  Semester: {cohort_218.semester}")
            self.stdout.write(f"  Registrations: {Registration.objects.filter(period=cohort_218).count()}")
            
            # Show students in this cohort
            students_in_cohort = Registration.objects.filter(period=cohort_218)
            self.stdout.write(f"\n👥 Students in cohort 218:")
            self.stdout.write(f"  Total students: {students_in_cohort.count()}")
            
            # Show sample students
            sample_students = students_in_cohort[:5]
            for i, reg in enumerate(sample_students, 1):
                self.stdout.write(f"    {i}. {reg.student.registration_number} - {reg.student.first_names} {reg.student.surname}")
        else:
            self.stdout.write(f"\n❌ COHORT 218 NOT FOUND")
        
        # Find August-December 2025 periods
        aug_dec_2025 = AcademicPeriod.objects.filter(name__icontains="2025").filter(name__icontains="august")
        
        if aug_dec_2025.exists():
            self.stdout.write(f"\n🎯 AUGUST-DECEMBER 2025 FOUND:")
            for period in aug_dec_2025:
                self.stdout.write(f"  Name: {period.name}")
                self.stdout.write(f"  External ID: {period.external_id}")
                self.stdout.write(f"  Academic Year: {period.academic_year}")
                self.stdout.write(f"  Semester: {period.semester}")
                self.stdout.write(f"  Registrations: {Registration.objects.filter(period=period).count()}")
        else:
            self.stdout.write(f"\n❌ AUGUST-DECEMBER 2025 NOT FOUND")
        
        # Show all 2025 periods
        all_2025 = AcademicPeriod.objects.filter(name__icontains="2025")
        if all_2025.exists():
            self.stdout.write(f"\n📅 ALL 2025 PERIODS:")
            for period in all_2025:
                reg_count = Registration.objects.filter(period=period).count()
                self.stdout.write(f"  {period.name} (ID: {period.external_id}) - {reg_count} registrations")
        
        # Show the relationship between academic years and cohorts
        self.stdout.write(f"\n🔗 COHORT STRUCTURE:")
        self.stdout.write(f"  - A cohort is identified by the academic period when students first register")
        self.stdout.write(f"  - Cohort 218 = August-December 2025 period")
        self.stdout.write(f"  - Academic Year 3 contains: August-December 2024 (ID: 214) and March-July 2025 (ID: 216)")
        self.stdout.write(f"  - Academic Year 4 contains: August-December 2025 (ID: 218)")
        
        # Show academic year 4 specifically
        self.stdout.write(f"\n📊 ACADEMIC YEAR 4:")
        year_4_periods = AcademicPeriod.objects.filter(academic_year=4)
        for period in year_4_periods:
            reg_count = Registration.objects.filter(period=period).count()
            self.stdout.write(f"  {period.name} (ID: {period.external_id}) - {reg_count} registrations")
            if period.external_id == 218:
                self.stdout.write(f"    ⭐ This is cohort 218!")
        
        # Show what academic years belong to cohort 218
        if cohort_218:
            self.stdout.write(f"\n🎓 ACADEMIC YEARS FOR COHORT 218 STUDENTS:")
            # Find all students who started in cohort 218 and track their progression
            cohort_218_students = Registration.objects.filter(period=cohort_218).values_list('student_id', flat=True)
            
            # Find all academic periods these students registered for
            student_progression = sorted(set(
                year for year in Registration.objects.filter(
                    student_id__in=cohort_218_students
                ).values_list('period__academic_year', flat=True) if year
            ))
            
            self.stdout.write(f"  Students in cohort 218 registered in these academic years:")
            for year in student_progression:
                self.stdout.write(f"    Academic Year {year}")
            
            # Show their progression timeline
            self.stdout.write(f"\n📈 PROGRESSION TIMELINE FOR COHORT 218:")
            all_periods_for_cohort = Registration.objects.filter(
                student_id__in=cohort_218_students
            ).values('period__name', 'period__academic_year', 'period__external_id').annotate(
                reg_count=models.Count('student_id')
            ).order_by('period__external_id')
            
            for period in all_periods_for_cohort:
                period_name = period['period__name']
                academic_year = period['period__academic_year']
                period_id = period['period__external_id']
                reg_count = period['reg_count']
                self.stdout.write(f"  {period_name} (Academic Year {academic_year}, ID: {period_id}) - {reg_count} students")

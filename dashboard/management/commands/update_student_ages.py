"""
Django management command to update student ages in real-time.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import Student
from services.age_service import AgeCalculator


class Command(BaseCommand):
    help = 'Update student ages based on current date'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of students to process in each batch',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS('Starting student age update...')
        )
        
        # Get all students with date of birth
        students_with_dob = Student.objects.filter(date_of_birth__isnull=False)
        total_students = students_with_dob.count()
        
        if total_students == 0:
            self.stdout.write(
                self.style.WARNING('No students with date of birth found.')
            )
            return
        
        self.stdout.write(
            f'Processing {total_students} students with date of birth...'
        )
        
        updated_count = 0
        error_count = 0
        
        # Process in batches
        for offset in range(0, total_students, batch_size):
            batch = students_with_dob[offset:offset + batch_size]
            
            for student in batch:
                try:
                    # Calculate current age
                    current_age = student.current_age
                    
                    if verbose:
                        self.stdout.write(
                            f'Student {student.registration_number}: {current_age} years old'
                        )
                    
                    # Check if age needs updating
                    if student.age != current_age:
                        if dry_run:
                            self.stdout.write(
                                f'Would update {student.registration_number}: '
                                f'{student.age} -> {current_age}'
                            )
                        else:
                            student.age = current_age
                            student.save(update_fields=['age'])
                            updated_count += 1
                            
                    elif verbose:
                        self.stdout.write(
                            f'No update needed for {student.registration_number}'
                        )
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error processing {student.registration_number}: {e}'
                        )
                    )
        
        # Summary
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Dry run completed. Would update {updated_count} student ages.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated {updated_count} student ages successfully.'
                )
            )
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'Encountered {error_count} errors.')
            )
        
        # Show statistics
        self.show_age_statistics()
    
    def show_age_statistics(self):
        """Display age statistics for all students."""
        self.stdout.write('\n' + self.style.SUCCESS('Age Statistics:'))
        
        ages = Student.objects.filter(
            date_of_birth__isnull=False
        ).values_list('current_age', flat=True)
        
        stats = AgeCalculator.get_age_statistics(list(ages))
        
        self.stdout.write(f'Total students with DOB: {stats["count"]}')
        self.stdout.write(f'Average age: {stats["average"]} years')
        self.stdout.write(f'Median age: {stats["median"]} years')
        self.stdout.write(f'Age range: {stats["min"]} - {stats["max"]} years')
        
        # Show age distribution
        self.stdout.write('\nAge Distribution:')
        
        age_categories = {
            'Under 18': 0,
            '18-19': 0,
            '20-21': 0,
            '22-24': 0,
            '25-29': 0,
            '30+': 0,
            'Unknown': 0
        }
        
        for student in Student.objects.all():
            category = AgeCalculator.categorize_age(student.current_age)
            age_categories[category] += 1
        
        for category, count in age_categories.items():
            if count > 0:
                percentage = (count / Student.objects.count()) * 100
                self.stdout.write(f'{category}: {count} ({percentage:.1f}%)')

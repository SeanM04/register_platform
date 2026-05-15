"""
Test final state of academic year distribution.
"""

from django.core.management.base import BaseCommand
from django.test import RequestFactory
from dashboard.demographics.services import build_demographic_data


class Command(BaseCommand):
    help = 'Test final academic year state'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Testing Final Academic Year State...')
        )
        
        factory = RequestFactory()
        
        # Test Period 201 specifically
        period_name = "May 2021 - August 2021"
        request = factory.get(f'/?period={period_name}')
        
        self.stdout.write(f'\n📅 Testing Period 201: {period_name}')
        
        try:
            demographic_data = build_demographic_data(request)
            year_distribution_rows = demographic_data.get("year_distribution_rows", [])
            
            actual_years = [int(row["year"]) for row in year_distribution_rows]
            # Chart payload always includes academic levels 1–5 for the filtered cohort.
            expected_levels = [1, 2, 3, 4, 5]
            self.stdout.write(f'🎯 Expected chart levels: {expected_levels}')
            self.stdout.write(f'📊 Actual chart levels: {actual_years}')
            if actual_years == expected_levels:
                self.stdout.write('✅ CORRECT: All five academic year levels are present.')
            else:
                self.stdout.write('❌ MISMATCH: Year distribution should always list 1–5.')
            
            # Show details
            self.stdout.write('\n📊 Detailed Results:')
            for row in year_distribution_rows:
                year = row["year"]
                total = row["total"]
                male = row["male"]
                female = row["female"]
                self.stdout.write(f'  Year {year}: {total} students (Male: {male}, Female: {female})')
                
        except Exception as e:
            self.stdout.write(f'❌ ERROR: {e}')
        
        self.stdout.write(
            self.style.SUCCESS('\nFinal state testing completed.')
        )

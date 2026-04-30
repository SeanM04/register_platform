"""
Age calculation utilities for real-time student age processing.
"""

from datetime import datetime, date
from django.utils import timezone
from typing import Dict, Optional, Union


class AgeCalculator:
    """Utility class for accurate age calculations."""
    
    @staticmethod
    def calculate_age(birth_date: Union[date, datetime, str], reference_date: Optional[Union[date, datetime]] = None) -> Optional[int]:
        """
        Calculate age in years as of reference date (or today if not provided).
        
        Args:
            birth_date: Date of birth (date, datetime, or string)
            reference_date: Reference date for calculation (defaults to today)
            
        Returns:
            Age in years or None if birth_date is invalid
        """
        if not birth_date:
            return None
            
        try:
            # Convert string to date if needed
            if isinstance(birth_date, str):
                birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            elif isinstance(birth_date, datetime):
                birth_date = birth_date.date()
                
            # Use today as reference if not provided
            if reference_date is None:
                reference_date = timezone.localdate()
            elif isinstance(reference_date, datetime):
                reference_date = reference_date.date()
                
            # Calculate age
            years = reference_date.year - birth_date.year
            
            # Adjust if birthday hasn't occurred yet this year
            if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
                years -= 1
                
            return years
            
        except (ValueError, TypeError, AttributeError):
            return None
    
    @staticmethod
    def calculate_detailed_age(birth_date: Union[date, datetime, str], reference_date: Optional[Union[date, datetime]] = None) -> Optional[Dict[str, int]]:
        """
        Calculate detailed age breakdown (years, months, days).
        
        Args:
            birth_date: Date of birth
            reference_date: Reference date for calculation (defaults to today)
            
        Returns:
            Dictionary with years, months, days or None if invalid
        """
        if not birth_date:
            return None
            
        try:
            # Convert to date objects
            if isinstance(birth_date, str):
                birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            elif isinstance(birth_date, datetime):
                birth_date = birth_date.date()
                
            if reference_date is None:
                reference_date = timezone.localdate()
            elif isinstance(reference_date, datetime):
                reference_date = reference_date.date()
                
            # Calculate years
            years = reference_date.year - birth_date.year
            months = reference_date.month - birth_date.month
            days = reference_date.day - birth_date.day
            
            # Adjust for negative values
            if days < 0:
                # Get days in previous month
                import calendar
                if reference_date.month == 1:
                    prev_month = 12
                    prev_year = reference_date.year - 1
                else:
                    prev_month = reference_date.month - 1
                    prev_year = reference_date.year
                
                days_in_prev_month = calendar.monthrange(prev_year, prev_month)[1]
                days += days_in_prev_month
                months -= 1
                
            if months < 0:
                months += 12
                years -= 1
                
            return {
                'years': years,
                'months': months,
                'days': days
            }
            
        except (ValueError, TypeError, AttributeError):
            return None
    
    @staticmethod
    def categorize_age(age: Optional[int]) -> str:
        """
        Categorize age into demographic groups.
        
        Args:
            age: Age in years
            
        Returns:
            Age category string
        """
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
            "25-29"
        else:
            return "30+"
    
    @staticmethod
    def format_age(age_details: Dict[str, int]) -> str:
        """
        Format age details into human-readable string.
        
        Args:
            age_details: Dictionary with years, months, days
            
        Returns:
            Formatted age string
        """
        if not age_details:
            return "Unknown"
            
        parts = []
        if age_details.get('years', 0) > 0:
            parts.append(f"{age_details['years']} years")
        if age_details.get('months', 0) > 0:
            parts.append(f"{age_details['months']} months")
        if age_details.get('days', 0) > 0:
            parts.append(f"{age_details['days']} days")
            
        return ", ".join(parts) if parts else "0 days"
    
    @staticmethod
    def is_adult(age: Optional[int]) -> Optional[bool]:
        """
        Check if person is adult (18 or older).
        
        Args:
            age: Age in years
            
        Returns:
            True if adult, False if minor, None if age unknown
        """
        if age is None:
            return None
        return age >= 18
    
    @staticmethod
    def get_age_statistics(ages: list) -> Dict[str, Union[int, float]]:
        """
        Calculate basic statistics for a list of ages.
        
        Args:
            ages: List of ages
            
        Returns:
            Dictionary with statistics
        """
        if not ages:
            return {
                'count': 0,
                'average': 0,
                'min': 0,
                'max': 0,
                'median': 0
            }
        
        # Filter out None values
        valid_ages = [age for age in ages if age is not None]
        
        if not valid_ages:
            return {
                'count': 0,
                'average': 0,
                'min': 0,
                'max': 0,
                'median': 0
            }
        
        valid_ages.sort()
        count = len(valid_ages)
        
        # Calculate median
        if count % 2 == 0:
            median = (valid_ages[count//2 - 1] + valid_ages[count//2]) / 2
        else:
            median = valid_ages[count//2]
        
        return {
            'count': count,
            'average': round(sum(valid_ages) / count, 1),
            'min': min(valid_ages),
            'max': max(valid_ages),
            'median': median
        }


# Convenience functions for common use cases
def calculate_student_age(birth_date, reference_date=None):
    """Quick function to calculate student age."""
    return AgeCalculator.calculate_age(birth_date, reference_date)

def get_detailed_student_age(birth_date, reference_date=None):
    """Quick function to get detailed student age."""
    return AgeCalculator.calculate_detailed_age(birth_date, reference_date)

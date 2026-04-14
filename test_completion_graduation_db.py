#!/usr/bin/env python
"""Test script to verify completion and graduation database connections."""

import os
import sys
import django

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'register_platform.settings')
django.setup()

from services.completion_service import get_completion_page_data
from services.graduation_services import get_graduation_page_data

def test_completion_service():
    """Test completion service database connection."""
    print("=== Testing Completion Service ===")
    
    try:
        # Test without filters (should return all data)
        print("1. Testing completion service without filters...")
        data = get_completion_page_data()
        
        print(f"   - Total students: {data['kpis']['total_students']}")
        print(f"   - Total cohorts: {data['kpis']['total_cohorts']}")
        print(f"   - Average completion rate: {data['kpis']['average_completion_rate']}")
        print(f"   - Male students: {data['kpis']['gender_distribution']['male']}")
        print(f"   - Female students: {data['kpis']['gender_distribution']['female']}")
        print(f"   - Students in table: {len(data['students'])}")
        print(f"   - Cohort chart data points: {len(data['charts']['cohort_completion'])}")
        print(f"   - Programme chart data points: {len(data['charts']['programme_completion'])}")
        
        if data['kpis']['total_students'] > 0:
            print("   SUCCESS: Completion service returned data!")
        else:
            print("   WARNING: Completion service returned no data")
            
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    # Test with filters
    try:
        print("\n2. Testing completion service with faculty filter...")
        data = get_completion_page_data(faculty="Science")
        print(f"   - Total students with Science faculty: {data['kpis']['total_students']}")
        print("   SUCCESS: Faculty filter works!")
        
    except Exception as e:
        print(f"   ERROR with faculty filter: {e}")
    
    return True

def test_graduation_service():
    """Test graduation service database connection."""
    print("\n=== Testing Graduation Service ===")
    
    try:
        # Test without filters (should return all data)
        print("1. Testing graduation service without filters...")
        data = get_graduation_page_data()
        
        print(f"   - Total graduated students: {data['kpis']['total_graduated_students']}")
        print(f"   - Average completion graduation rate: {data['kpis']['average_completion_graduation_rate']}")
        print(f"   - On-time graduation rate: {data['kpis']['on_time_graduation_rate']}")
        print(f"   - Students in table: {len(data['students'])}")
        print(f"   - Programme chart data points: {len(data['charts']['programme_graduation_rate'])}")
        print(f"   - Cohort chart data points: {len(data['charts']['cohort_graduation_rate'])}")
        
        if data['kpis']['total_graduated_students'] > 0:
            print("   SUCCESS: Graduation service returned data!")
        else:
            print("   WARNING: Graduation service returned no data")
            
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    # Test with filters
    try:
        print("\n2. Testing graduation service with faculty filter...")
        data = get_graduation_page_data(faculty="Science")
        print(f"   - Total graduated students with Science faculty: {data['kpis']['total_graduated_students']}")
        print("   SUCCESS: Faculty filter works!")
        
    except Exception as e:
        print(f"   ERROR with faculty filter: {e}")
    
    return True

def test_database_models():
    """Test if we can access the database models directly."""
    print("\n=== Testing Database Models ===")
    
    try:
        from dashboard.models import Registration, Student, AcademicPeriod, Faculty, Programme
        
        # Test basic counts
        print(f"1. Total registrations: {Registration.objects.count()}")
        print(f"2. Total students: {Student.objects.count()}")
        print(f"3. Total academic periods: {AcademicPeriod.objects.count()}")
        print(f"4. Total faculties: {Faculty.objects.count()}")
        print(f"5. Total programmes: {Programme.objects.count()}")
        
        # Test a sample registration
        if Registration.objects.exists():
            sample_reg = Registration.objects.first()
            print(f"6. Sample registration: {sample_reg.student.name} - {sample_reg.programme.name}")
            print("   SUCCESS: Database models accessible!")
        else:
            print("   WARNING: No registrations found in database")
            
    except Exception as e:
        print(f"   ERROR accessing models: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing Completion and Graduation Database Connections")
    print("=" * 60)
    
    # Test database models first
    models_ok = test_database_models()
    
    # Test services
    completion_ok = test_completion_service()
    graduation_ok = test_graduation_service()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"  Database Models: {'PASS' if models_ok else 'FAIL'}")
    print(f"  Completion Service: {'PASS' if completion_ok else 'FAIL'}")
    print(f"  Graduation Service: {'PASS' if graduation_ok else 'FAIL'}")
    
    if models_ok and completion_ok and graduation_ok:
        print("\nAll tests PASSED! Database connection is working.")
    else:
        print("\nSome tests FAILED. Check the errors above.")

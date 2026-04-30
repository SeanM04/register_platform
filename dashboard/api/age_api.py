"""
API endpoints for real-time age calculations.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from dashboard.models import Student
from services.age_service import AgeCalculator
import json


@method_decorator(csrf_exempt, name='dispatch')
class StudentAgeAPI(View):
    """API endpoint for real-time student age calculations."""
    
    def get(self, request):
        """Get age information for a specific student."""
        registration_number = request.GET.get('registration_number')
        
        if not registration_number:
            return JsonResponse({
                'error': 'Registration number is required',
                'status': 'error'
            }, status=400)
        
        try:
            student = Student.objects.get(registration_number__iexact=registration_number)
            
            age_data = {
                'registration_number': student.registration_number,
                'full_name': student.full_name,
                'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
                'current_age': student.current_age,
                'age_details': student.age_with_details,
                'age_category': student.age_category,
                'is_adult': AgeCalculator.is_adult(student.current_age)
            }
            
            return JsonResponse({
                'data': age_data,
                'status': 'success'
            })
            
        except Student.DoesNotExist:
            return JsonResponse({
                'error': 'Student not found',
                'status': 'error'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'status': 'error'
            }, status=500)
    
    def post(self, request):
        """Calculate age for any date (utility endpoint)."""
        try:
            data = json.loads(request.body)
            birth_date = data.get('birth_date')
            reference_date = data.get('reference_date')
            
            if not birth_date:
                return JsonResponse({
                    'error': 'Birth date is required',
                    'status': 'error'
                }, status=400)
            
            # Calculate age
            age = AgeCalculator.calculate_age(birth_date, reference_date)
            detailed_age = AgeCalculator.calculate_detailed_age(birth_date, reference_date)
            
            result = {
                'birth_date': birth_date,
                'reference_date': reference_date or 'today',
                'age': age,
                'age_details': detailed_age,
                'formatted_age': AgeCalculator.format_age(detailed_age) if detailed_age else None,
                'age_category': AgeCalculator.categorize_age(age),
                'is_adult': AgeCalculator.is_adult(age)
            }
            
            return JsonResponse({
                'data': result,
                'status': 'success'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON data',
                'status': 'error'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'status': 'error'
            }, status=500)


@require_http_methods(["GET"])
def age_statistics_api(request):
    """API endpoint for age statistics across all students."""
    try:
        # Get all ages
        ages = Student.objects.filter(
            date_of_birth__isnull=False
        ).values_list('current_age', flat=True)
        
        # Calculate statistics
        stats = AgeCalculator.get_age_statistics(list(ages))
        
        # Get age distribution
        age_distribution = {}
        for student in Student.objects.all():
            category = AgeCalculator.categorize_age(student.current_age)
            age_distribution[category] = age_distribution.get(category, 0) + 1
        
        # Calculate percentages
        total_students = Student.objects.count()
        age_distribution_percentages = {}
        for category, count in age_distribution.items():
            age_distribution_percentages[category] = {
                'count': count,
                'percentage': round((count / total_students) * 100, 1) if total_students > 0 else 0
            }
        
        return JsonResponse({
            'data': {
                'statistics': stats,
                'distribution': age_distribution_percentages,
                'total_students': total_students,
                'students_with_dob': len([age for age in ages if age is not None])
            },
            'status': 'success'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def batch_age_calculation_api(request):
    """Calculate ages for multiple students at once."""
    try:
        data = json.loads(request.body)
        registration_numbers = data.get('registration_numbers', [])
        
        if not registration_numbers:
            return JsonResponse({
                'error': 'Registration numbers list is required',
                'status': 'error'
            }, status=400)
        
        results = []
        errors = []
        
        for reg_number in registration_numbers:
            try:
                student = Student.objects.get(registration_number__iexact=reg_number)
                
                age_data = {
                    'registration_number': student.registration_number,
                    'full_name': student.full_name,
                    'current_age': student.current_age,
                    'age_category': student.age_category
                }
                results.append(age_data)
                
            except Student.DoesNotExist:
                errors.append({
                    'registration_number': reg_number,
                    'error': 'Student not found'
                })
            except Exception as e:
                errors.append({
                    'registration_number': reg_number,
                    'error': str(e)
                })
        
        return JsonResponse({
            'data': {
                'results': results,
                'errors': errors,
                'processed': len(registration_numbers),
                'successful': len(results),
                'failed': len(errors)
            },
            'status': 'success'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data',
            'status': 'error'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)

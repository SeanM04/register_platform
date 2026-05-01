"""
URL configuration for age API endpoints.
"""

from django.urls import path
from . import age_api

app_name = 'age_api'

urlpatterns = [
    # Student age endpoints
    path('student/', age_api.StudentAgeAPI.as_view(), name='student_age'),
    path('calculate/', age_api.StudentAgeAPI.as_view(), name='calculate_age'),
    
    # Statistics endpoints
    path('statistics/', age_api.age_statistics_api, name='age_statistics'),
    path('batch/', age_api.batch_age_calculation_api, name='batch_age_calculation'),
]

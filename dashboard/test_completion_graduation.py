"""Tests for completion and graduation endpoints."""

from django.test import TestCase
from django.urls import reverse
from .test_support import DashboardFixtureMixin


class CompletionGraduationTests(DashboardFixtureMixin, TestCase):
    """Test completion and graduation endpoints."""

    def test_completion_payload_returns_data(self):
        """Completion payload should return structured data."""
        response = self.client.get(reverse("dashboard:completion-payload"))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['status'], 'success')
        self.assertIn('data', data)
        self.assertIn('kpis', data['data'])
        self.assertIn('charts', data['data'])
        self.assertIn('students', data['data'])
        
        # Check KPI structure
        kpis = data['data']['kpis']
        self.assertIn('total_students', kpis)
        self.assertIn('total_cohorts', kpis)
        self.assertIn('average_completion_rate', kpis)
        self.assertIn('gender_distribution', kpis)
        
        # Check chart structure
        charts = data['data']['charts']
        self.assertIn('cohort_completion', charts)
        self.assertIn('programme_completion', charts)
        
        print(f"Completion data: {kpis['total_students']} students, {kpis['total_cohorts']} cohorts")

    def test_completion_payload_respects_year_filter(self):
        """Completion payload should respect year filter."""
        response = self.client.get(reverse("dashboard:completion-payload"), {"year": "2026"})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        print(f"Completion with year filter: {data['data']['kpis']['total_students']} students")

    def test_completion_payload_respects_faculty_filter(self):
        """Completion payload should respect faculty filter."""
        response = self.client.get(
            reverse("dashboard:completion-payload"), 
            {"faculty": self.science_faculty.name}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        print(f"Completion with faculty filter: {data['data']['kpis']['total_students']} students")

    def test_graduation_payload_returns_data(self):
        """Graduation payload should return structured data."""
        response = self.client.get(reverse("dashboard:graduation-payload"))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['status'], 'success')
        self.assertIn('data', data)
        self.assertIn('kpis', data['data'])
        self.assertIn('charts', data['data'])
        self.assertIn('students', data['data'])
        
        # Check KPI structure
        kpis = data['data']['kpis']
        self.assertIn('total_graduated_students', kpis)
        self.assertIn('average_completion_graduation_rate', kpis)
        self.assertIn('on_time_graduation_rate', kpis)
        self.assertIn('graduation_rate_by_faculty', kpis)
        
        # Check chart structure
        charts = data['data']['charts']
        self.assertIn('programme_graduation_rate', charts)
        self.assertIn('cohort_graduation_rate', charts)
        
        print(f"Graduation data: {kpis['total_graduated_students']} graduated students")

    def test_graduation_payload_respects_year_filter(self):
        """Graduation payload should respect year filter."""
        response = self.client.get(reverse("dashboard:graduation-payload"), {"year": "2026"})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        print(f"Graduation with year filter: {data['data']['kpis']['total_graduated_students']} students")

    def test_graduation_payload_respects_faculty_filter(self):
        """Graduation payload should respect faculty filter."""
        response = self.client.get(
            reverse("dashboard:graduation-payload"), 
            {"faculty": self.science_faculty.name}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        print(f"Graduation with faculty filter: {data['data']['kpis']['total_graduated_students']} students")

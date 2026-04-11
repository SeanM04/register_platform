"""
Completion Analysis Service
Handles all completion-related data processing and analysis.
"""

import pandas as pd
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CompletionService:
    """Service for completion analysis data processing."""
    
    def __init__(self):
        self.registration_data = None
        self.course_data = None
        self._load_data()
    
    def _load_data(self):
        """Load data from CSV files."""
        try:
            # Load registration data
            self.registration_data = pd.read_csv('data/registration.csv')
            
            # Load course final marks data
            self.course_data = pd.read_csv('data/course_final_marks.csv')
            
            logger.info("Successfully loaded completion data")
            
        except FileNotFoundError as e:
            logger.warning(f"Data files not found: {e}")
            logger.info("Creating sample data for demonstration purposes")
            self._create_sample_data()
        except Exception as e:
            logger.error(f"Error loading completion data: {e}")
            self._create_sample_data()
    
    def _create_sample_data(self):
        """Create sample data when CSV files are not available."""
        import numpy as np
        
        # Sample registration data
        sample_registrations = []
        programmes = [
            (1, 'Computer Science', 'Science'),
            (2, 'Engineering', 'Engineering'),
            (3, 'Business Studies', 'Business'),
            (4, 'Mathematics', 'Science'),
            (5, 'Physics', 'Science')
        ]
        
        for i in range(1, 501):  # 500 students
            programme_id = np.random.choice([p[0] for p in programmes])
            programme_info = next(p for p in programmes if p[0] == programme_id)
            
            sample_registrations.append({
                'regnum': f'STD{i:03d}',
                'student_name': f'Student {i}',
                'programme_id': programme_id,
                'programme_name': programme_info[1],
                'faculty': programme_info[2],
                'academic_year': np.random.choice([2021, 2022, 2023, 2024]),
                'semester': np.random.choice([1, 2]),
                'cohort_period_id': np.random.choice([1, 2, 3, 4]),
                'academic_stage': np.random.choice(['[1,1]', '[2,1]', '[3,1]', '[4,1]', '[4,2]']),
                'gender': np.random.choice(['M', 'F']),
                'decision': np.random.choice(['PROCEED', 'REPEAT', 'DEFERRED'])
            })
        
        self.registration_data = pd.DataFrame(sample_registrations)
        
        # Sample course data
        sample_courses = []
        for i in range(1, 501):
            for course in ['CS101', 'MATH201', 'ENG301', 'BUS401']:
                sample_courses.append({
                    'regnum': f'STD{i:03d}',
                    'course_code': course,
                    'final_mark': np.random.randint(40, 95),
                    'academic_year': np.random.choice([2021, 2022, 2023, 2024]),
                    'semester': np.random.choice([1, 2])
                })
        
        self.course_data = pd.DataFrame(sample_courses)
        logger.info("Created sample data for demonstration")
    
    def get_completion_page_data(self, academic_year: Optional[str] = None, 
                              semester: Optional[str] = None,
                              faculty: Optional[str] = None,
                              programme_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete page data for completion analysis.
        
        Args:
            academic_year: Filter by academic year
            semester: Filter by semester (1 or 2)
            faculty: Filter by faculty
            programme_id: Filter by programme ID
            
        Returns:
            Dictionary containing KPIs, charts data, and students data
        """
        try:
            # Apply filters
            filtered_data = self._apply_filters(
                academic_year=academic_year,
                semester=semester,
                faculty=faculty,
                programme_id=programme_id
            )
            
            # Calculate KPIs
            kpis = self._calculate_kpis(filtered_data)
            
            # Generate chart data
            charts = self._generate_charts(filtered_data)
            
            # Get student details
            students = self._get_student_details(filtered_data)
            
            # Return data as-is, Django encoder will handle JSON serialization
            result = {
                'kpis': kpis,
                'charts': charts,
                'students': students
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting completion page data: {e}")
            raise
    
        
    def _apply_filters(self, academic_year: Optional[str] = None,
                     semester: Optional[str] = None,
                     faculty: Optional[str] = None,
                     programme_id: Optional[str] = None) -> pd.DataFrame:
        """Apply filters to the data."""
        filtered_data = self.registration_data.copy()
        
        if academic_year:
            filtered_data = filtered_data[filtered_data['academic_year'] == int(academic_year)]
        
        if semester:
            filtered_data = filtered_data[filtered_data['semester'] == int(semester)]
        
        if faculty:
            filtered_data = filtered_data[filtered_data['faculty'] == faculty]
        
        if programme_id:
            filtered_data = filtered_data[filtered_data['programme_id'] == int(programme_id)]
        
        return filtered_data
    
    def _calculate_kpis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate key performance indicators."""
        try:
            # Total students
            total_students = len(data['regnum'].unique())
            
            # Total cohorts
            total_cohorts = len(data['cohort_period_id'].unique())
            
            # Average completion rate
            avg_completion_rate = self._calculate_average_completion_rate(data)
            
            # Gender distribution
            gender_dist = data.groupby('gender')['regnum'].nunique().to_dict()
            
            return {
                'total_students': int(total_students),
                'total_cohorts': int(total_cohorts),
                'average_completion_rate': float(round(avg_completion_rate, 1)),
                'gender_distribution': {
                    'male': int(gender_dist.get('M', 0)),
                    'female': int(gender_dist.get('F', 0)),
                    'other': int(gender_dist.get('O', 0))
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating KPIs: {e}")
            return {}
    
    def _calculate_average_completion_rate(self, data: pd.DataFrame) -> float:
        """Calculate average completion rate."""
        try:
            # Group by student and calculate completion
            student_completion = data.groupby('regnum').agg({
                'academic_stage': 'max',  # Get highest academic stage
                'programme_id': 'first'
            }).reset_index()
            
            # Define completion criteria (e.g., reaching stage [4,1] or higher)
            completed_students = student_completion[
                student_completion['academic_stage'].astype(str).str.contains('4,1|4,2|5,1|5,2')
            ]
            
            completion_rate = (len(completed_students) / len(student_completion)) * 100
            return completion_rate
            
        except Exception as e:
            logger.error(f"Error calculating completion rate: {e}")
            return 0.0
    
    def _generate_charts(self, data: pd.DataFrame) -> Dict[str, List[Dict]]:
        """Generate chart data."""
        try:
            # Cohort completion chart
            cohort_data = self._get_cohort_completion_data(data)
            
            # Programme completion chart
            programme_data = self._get_programme_completion_data(data)
            
            return {
                'cohort_completion': cohort_data,
                'programme_completion': programme_data
            }
            
        except Exception as e:
            logger.error(f"Error generating charts: {e}")
            return {'cohort_completion': [], 'programme_completion': []}
    
    def _get_cohort_completion_data(self, data: pd.DataFrame) -> List[Dict]:
        """Get cohort completion data for charting."""
        try:
            cohort_stats = []
            
            for cohort_id in sorted(data['cohort_period_id'].unique()):
                cohort_data = data[data['cohort_period_id'] == cohort_id]
                
                # Calculate completion rate for this cohort
                initial_students = len(cohort_data['regnum'].unique())
                completion_rate = self._calculate_cohort_completion_rate(cohort_data)
                
                cohort_stats.append({
                    'cohort_period_id': int(cohort_id),
                    'initial_students': int(initial_students),
                    'current_students': int(len(cohort_data['regnum'].unique())),
                    'completion_rate': float(round(completion_rate, 1))
                })
            
            return cohort_stats
            
        except Exception as e:
            logger.error(f"Error getting cohort completion data: {e}")
            return []
    
    def _calculate_cohort_completion_rate(self, cohort_data: pd.DataFrame) -> float:
        """Calculate completion rate for a specific cohort."""
        try:
            student_stages = cohort_data.groupby('regnum')['academic_stage'].max()
            
            completed = sum(
                student_stages.astype(str).str.contains('4,1|4,2|5,1|5,2')
            )
            
            return (completed / len(student_stages)) * 100 if len(student_stages) > 0 else 0
            
        except Exception as e:
            logger.error(f"Error calculating cohort completion rate: {e}")
            return 0.0
    
    def _get_programme_completion_data(self, data: pd.DataFrame) -> List[Dict]:
        """Get programme completion data for charting."""
        try:
            programme_stats = []
            
            for programme_id in sorted(data['programme_id'].unique()):
                programme_data = data[data['programme_id'] == programme_id]
                
                # Get programme name
                programme_name = programme_data['programme_name'].iloc[0] if not programme_data.empty else f"Programme {programme_id}"
                
                # Calculate completion rate
                completion_rate = self._calculate_cohort_completion_rate(programme_data)
                
                programme_stats.append({
                    'programme_id': int(programme_id),
                    'programme_name': str(programme_name),
                    'completion_rate': float(round(completion_rate, 1))
                })
            
            # Sort by completion rate
            programme_stats.sort(key=lambda x: x['completion_rate'], reverse=True)
            
            return programme_stats
            
        except Exception as e:
            logger.error(f"Error getting programme completion data: {e}")
            return []
    
    def _get_student_details(self, data: pd.DataFrame) -> List[Dict]:
        """Get detailed student information."""
        try:
            student_details = []
            
            for regnum in data['regnum'].unique():
                student_data = data[data['regnum'] == regnum].iloc[-1]  # Get latest record
                
                # Calculate completion rate
                completion_rate = self._calculate_student_completion_rate(regnum, data)
                
                # Calculate graduation rate (if applicable)
                graduation_rate = self._calculate_student_graduation_rate(regnum, data)
                
                student_details.append({
                    'regnum': str(regnum),
                    'student_name': str(student_data['student_name']),
                    'programme_name': str(student_data['programme_name']),
                    'academic_stage': str(student_data['academic_stage']),
                    'decision': str(student_data.get('decision', 'PROCEED')),
                    'completion_rate': float(round(completion_rate, 1)),
                    'graduation_rate': float(round(graduation_rate, 1)) if graduation_rate > 0 else None
                })
            
            return student_details
            
        except Exception as e:
            logger.error(f"Error getting student details: {e}")
            return []
    
    def _calculate_student_completion_rate(self, regnum: str, data: pd.DataFrame) -> float:
        """Calculate completion rate for a specific student."""
        try:
            student_data = data[data['regnum'] == regnum]
            max_stage = student_data['academic_stage'].max()
            
            # Simple completion calculation based on academic stage
            if str(max_stage) in ['4,1', '4,2', '5,1', '5,2']:
                return 100.0
            elif str(max_stage) in ['3,1', '3,2']:
                return 75.0
            elif str(max_stage) in ['2,1', '2,2']:
                return 50.0
            else:
                return 25.0
                
        except Exception as e:
            logger.error(f"Error calculating student completion rate: {e}")
            return 0.0
    
    def _calculate_student_graduation_rate(self, regnum: str, data: pd.DataFrame) -> float:
        """Calculate graduation rate for a specific student."""
        try:
            student_data = data[data['regnum'] == regnum]
            max_stage = student_data['academic_stage'].max()
            
            # Simple graduation calculation
            if str(max_stage) in ['4,2', '5,2']:
                return 100.0
            elif str(max_stage) in ['4,1', '5,1']:
                return 90.0
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error calculating student graduation rate: {e}")
            return 0.0
    
    def get_programmes(self) -> List[Dict[str, Any]]:
        """Get list of available programmes."""
        try:
            programmes = self.registration_data[['programme_id', 'programme_name']].drop_duplicates()
            return programmes.astype(object).to_dict('records')
        except Exception as e:
            logger.error(f"Error getting programmes: {e}")
            return []
    
    def get_faculties(self) -> List[Dict[str, Any]]:
        """Get list of available faculties."""
        try:
            faculties = self.registration_data[['faculty']].drop_duplicates()
            return faculties.astype(object).to_dict('records')
        except Exception as e:
            logger.error(f"Error getting faculties: {e}")
            return []
    
    def get_academic_years(self) -> List[Dict[str, Any]]:
        """Get list of available academic years."""
        try:
            years = self.registration_data[['academic_year']].drop_duplicates().sort_values('academic_year')
            return years.astype(object).to_dict('records')
        except Exception as e:
            logger.error(f"Error getting academic years: {e}")
            return []


# Global service instance
completion_service = CompletionService()


def get_completion_page_data(academic_year: Optional[str] = None,
                          semester: Optional[str] = None,
                          faculty: Optional[str] = None,
                          programme_id: Optional[str] = None) -> Dict[str, Any]:
    """Get completion page data."""
    return completion_service.get_completion_page_data(
        academic_year=academic_year,
        semester=semester,
        faculty=faculty,
        programme_id=programme_id
    )


def get_completion_programmes() -> List[Dict[str, Any]]:
    """Get available programmes for completion analysis."""
    return completion_service.get_programmes()


def get_completion_faculties() -> List[Dict[str, Any]]:
    """Get available faculties for completion analysis."""
    return completion_service.get_faculties()


def get_completion_academic_years() -> List[Dict[str, Any]]:
    """Get available academic years for completion analysis."""
    return completion_service.get_academic_years()

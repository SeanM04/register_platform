"""
Graduation Analysis Service
Handles all graduation-related data processing and analysis.
"""

import pandas as pd
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class GraduationService:
    """Service for graduation analysis data processing."""
    
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
            
            logger.info("Successfully loaded graduation data")
            
        except FileNotFoundError as e:
            logger.warning(f"Data files not found: {e}")
            logger.info("Creating sample data for demonstration purposes")
            self._create_sample_data()
        except Exception as e:
            logger.error(f"Error loading graduation data: {e}")
            self._create_sample_data()
    
    def _create_sample_data(self):
        """Create sample data when CSV files are not available."""
        import numpy as np
        
        # Sample registration data with graduation focus
        sample_registrations = []
        programmes = [
            (1, 'Computer Science', 'Science'),
            (2, 'Engineering', 'Engineering'),
            (3, 'Business Studies', 'Business'),
            (4, 'Mathematics', 'Science'),
            (5, 'Physics', 'Science')
        ]
        
        for i in range(1, 301):  # 300 students
            programme_id = np.random.choice([p[0] for p in programmes])
            programme_info = next(p for p in programmes if p[0] == programme_id)
            
            # Create more graduated students for demonstration
            academic_stage = np.random.choice(['[1,1]', '[2,1]', '[3,1]', '[4,1]', '[4,2]', '[5,2]'], 
                                                p=[0.1, 0.15, 0.2, 0.25, 0.2, 0.1])
            
            sample_registrations.append({
                'regnum': f'GRD{i:03d}',
                'student_name': f'Graduated {i}',
                'programme_id': programme_id,
                'programme_name': programme_info[1],
                'faculty': programme_info[2],
                'academic_year': np.random.choice([2021, 2022, 2023, 2024]),
                'semester': np.random.choice([1, 2]),
                'cohort_period_id': np.random.choice([1, 2, 3, 4]),
                'academic_stage': academic_stage,
                'gender': np.random.choice(['M', 'F']),
                'decision': np.random.choice(['PROCEED', 'GRADUATED'])
            })
        
        self.registration_data = pd.DataFrame(sample_registrations)
        
        # Sample course data
        sample_courses = []
        for i in range(1, 301):
            for course in ['CS101', 'MATH201', 'ENG301', 'BUS401']:
                sample_courses.append({
                    'regnum': f'GRD{i:03d}',
                    'course_code': course,
                    'final_mark': np.random.randint(50, 95),  # Higher marks for graduates
                    'academic_year': np.random.choice([2021, 2022, 2023, 2024]),
                    'semester': np.random.choice([1, 2])
                })
        
        self.course_data = pd.DataFrame(sample_courses)
        logger.info("Created sample graduation data for demonstration")
    
    def get_graduation_page_data(self, faculty: Optional[str] = None,
                               programme_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete page data for graduation analysis.
        
        Args:
            faculty: Filter by faculty
            programme_id: Filter by programme ID
            
        Returns:
            Dictionary containing KPIs, charts data, and students data
        """
        try:
            # Apply filters
            filtered_data = self._apply_filters(
                faculty=faculty,
                programme_id=programme_id
            )
            
            # Calculate KPIs
            kpis = self._calculate_kpis(filtered_data)
            
            # Generate chart data
            charts = self._generate_charts(filtered_data)
            
            # Get graduated students
            students = self._get_graduated_students(filtered_data)
            
            # Return data as-is, Django encoder will handle JSON serialization
            result = {
                'kpis': kpis,
                'charts': charts,
                'students': students
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting graduation page data: {e}")
            raise
    
        
    def _apply_filters(self, faculty: Optional[str] = None,
                     programme_id: Optional[str] = None) -> pd.DataFrame:
        """Apply filters to the data."""
        filtered_data = self.registration_data.copy()
        
        if faculty:
            filtered_data = filtered_data[filtered_data['faculty'] == faculty]
        
        if programme_id:
            filtered_data = filtered_data[filtered_data['programme_id'] == int(programme_id)]
        
        return filtered_data
    
    def _calculate_kpis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate key performance indicators."""
        try:
            # Get graduated students
            graduated_students = self._get_graduated_students_data(data)
            
            # Total graduated students
            total_graduated = len(graduated_students)
            
            # Average completion graduation rate
            avg_completion_grad_rate = self._calculate_average_completion_graduation_rate(graduated_students)
            
            # On-time graduation rate
            on_time_grad_rate = self._calculate_on_time_graduation_rate(graduated_students)
            
            # Graduation rate by faculty
            faculty_grad_rates = self._calculate_faculty_graduation_rates(data)
            
            return {
                'total_graduated_students': int(total_graduated),
                'average_completion_graduation_rate': float(round(avg_completion_grad_rate, 1)),
                'on_time_graduation_rate': float(round(on_time_grad_rate, 1)),
                'graduation_rate_by_faculty': {k: float(v) for k, v in faculty_grad_rates.items()}
            }
            
        except Exception as e:
            logger.error(f"Error calculating KPIs: {e}")
            return {}
    
    def _get_graduated_students_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Get data for graduated students only."""
        try:
            # Define graduation criteria based on academic stage
            graduated = data[
                data['academic_stage'].astype(str).isin(['4,2', '5,2'])  # Final stages
            ].copy()
            
            return graduated
            
        except Exception as e:
            logger.error(f"Error getting graduated students data: {e}")
            return pd.DataFrame()
    
    def _calculate_average_completion_graduation_rate(self, graduated_students: pd.DataFrame) -> float:
        """Calculate average completion graduation rate."""
        try:
            if graduated_students.empty:
                return 0.0
            
            # Calculate graduation rate for each student
            graduation_rates = graduated_students.groupby('regnum').apply(
                lambda x: self._calculate_student_graduation_rate(x.iloc[0])
            )
            
            return graduation_rates.mean()
            
        except Exception as e:
            logger.error(f"Error calculating average completion graduation rate: {e}")
            return 0.0
    
    def _calculate_on_time_graduation_rate(self, graduated_students: pd.DataFrame) -> float:
        """Calculate on-time graduation rate."""
        try:
            if graduated_students.empty:
                return 0.0
            
            # Define on-time criteria (e.g., completed within expected duration)
            # This is simplified - in reality, you'd track actual vs expected graduation time
            on_time_count = 0
            total_graduated = len(graduated_students['regnum'].unique())
            
            for regnum in graduated_students['regnum'].unique():
                student_data = graduated_students[graduated_students['regnum'] == regnum]
                if self._is_on_time_graduation(student_data):
                    on_time_count += 1
            
            return (on_time_count / total_graduated) * 100 if total_graduated > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating on-time graduation rate: {e}")
            return 0.0
    
    def _is_on_time_graduation(self, student_data: pd.DataFrame) -> bool:
        """Check if student graduated on time."""
        try:
            # Simplified logic - in reality, you'd compare actual vs expected graduation time
            max_stage = student_data['academic_stage'].max()
            
            # Assume 4,2 is on-time for 4-year programs, 5,2 for 5-year programs
            if str(max_stage) == '4,2':
                return True
            elif str(max_stage) == '5,2':
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error checking on-time graduation: {e}")
            return False
    
    def _calculate_faculty_graduation_rates(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate graduation rates by faculty."""
        try:
            faculty_rates = {}
            
            for faculty in data['faculty'].unique():
                faculty_data = data[data['faculty'] == faculty]
                graduated = self._get_graduated_students_data(faculty_data)
                total_students = len(faculty_data['regnum'].unique())
                
                if total_students > 0:
                    grad_rate = (len(graduated['regnum'].unique()) / total_students) * 100
                    faculty_rates[faculty] = round(grad_rate, 1)
                else:
                    faculty_rates[faculty] = 0.0
            
            return faculty_rates
            
        except Exception as e:
            logger.error(f"Error calculating faculty graduation rates: {e}")
            return {}
    
    def _generate_charts(self, data: pd.DataFrame) -> Dict[str, List[Dict]]:
        """Generate chart data."""
        try:
            # Programme graduation chart
            programme_data = self._get_programme_graduation_data(data)
            
            # Cohort graduation chart
            cohort_data = self._get_cohort_graduation_data(data)
            
            return {
                'programme_graduation_rate': programme_data,
                'cohort_graduation_rate': cohort_data
            }
            
        except Exception as e:
            logger.error(f"Error generating charts: {e}")
            return {'programme_graduation_rate': [], 'cohort_graduation_rate': []}
    
    def _get_programme_graduation_data(self, data: pd.DataFrame) -> List[Dict]:
        """Get programme graduation data for charting."""
        try:
            programme_stats = []
            
            for programme_id in sorted(data['programme_id'].unique()):
                programme_data = data[data['programme_id'] == programme_id]
                
                # Get programme name
                programme_name = programme_data['programme_name'].iloc[0] if not programme_data.empty else f"Programme {programme_id}"
                
                # Calculate graduation rate
                graduation_rate = self._calculate_programme_graduation_rate(programme_data)
                
                programme_stats.append({
                    'programme_name': str(programme_name),
                    'graduation_rate': float(round(graduation_rate, 1))
                })
            
            # Sort by graduation rate
            programme_stats.sort(key=lambda x: x['graduation_rate'], reverse=True)
            
            return programme_stats
            
        except Exception as e:
            logger.error(f"Error getting programme graduation data: {e}")
            return []
    
    def _calculate_programme_graduation_rate(self, programme_data: pd.DataFrame) -> float:
        """Calculate graduation rate for a specific programme."""
        try:
            total_students = len(programme_data['regnum'].unique())
            graduated = self._get_graduated_students_data(programme_data)
            graduated_count = len(graduated['regnum'].unique())
            
            return (graduated_count / total_students) * 100 if total_students > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating programme graduation rate: {e}")
            return 0.0
    
    def _get_cohort_graduation_data(self, data: pd.DataFrame) -> List[Dict]:
        """Get cohort graduation data for charting."""
        try:
            cohort_stats = []
            
            for cohort_id in sorted(data['cohort_period_id'].unique()):
                cohort_data = data[data['cohort_period_id'] == cohort_id]
                
                # Calculate graduation rate for this cohort
                graduation_rate = self._calculate_programme_graduation_rate(cohort_data)
                
                cohort_stats.append({
                    'cohort_period_id': int(cohort_id),
                    'graduation_rate': float(round(graduation_rate, 1))
                })
            
            return cohort_stats
            
        except Exception as e:
            logger.error(f"Error getting cohort graduation data: {e}")
            return []
    
    def _get_graduated_students(self, data: pd.DataFrame) -> List[Dict]:
        """Get detailed information about graduated students."""
        try:
            graduated_data = self._get_graduated_students_data(data)
            student_details = []
            
            for regnum in graduated_data['regnum'].unique():
                student_data = graduated_data[graduated_data['regnum'] == regnum].iloc[-1]
                
                # Calculate graduation rate
                graduation_rate = self._calculate_student_graduation_rate(student_data)
                
                student_details.append({
                    'regnum': str(regnum),
                    'student_name': str(student_data['student_name']),
                    'programme_name': str(student_data['programme_name']),
                    'faculty': str(student_data['faculty']),
                    'graduation_rate': float(round(graduation_rate, 1))
                })
            
            return student_details
            
        except Exception as e:
            logger.error(f"Error getting graduated students: {e}")
            return []
    
    def _calculate_student_graduation_rate(self, student_data: pd.Series) -> float:
        """Calculate graduation rate for a specific student."""
        try:
            # Calculate based on academic stage and performance
            max_stage = student_data['academic_stage']
            
            # Simple graduation rate calculation
            if str(max_stage) == '5,2':
                return 95.0  # 5-year engineering program
            elif str(max_stage) == '4,2':
                return 90.0  # 4-year program
            elif str(max_stage) == '2,2':
                return 85.0  # Masters program
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


# Global service instance
graduation_service = GraduationService()


def get_graduation_page_data(faculty: Optional[str] = None,
                           programme_id: Optional[str] = None) -> Dict[str, Any]:
    """Get graduation page data."""
    return graduation_service.get_graduation_page_data(
        faculty=faculty,
        programme_id=programme_id
    )


def get_graduation_programmes() -> List[Dict[str, Any]]:
    """Get available programmes for graduation analysis."""
    return graduation_service.get_programmes()


def get_graduation_faculties() -> List[Dict[str, Any]]:
    """Get available faculties for graduation analysis."""
    return graduation_service.get_faculties()

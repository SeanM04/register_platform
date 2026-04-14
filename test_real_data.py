from services.completion_service import get_completion_page_data
from services.graduation_services import get_graduation_page_data

print('=== Testing Completion Service with Real Data ===')
data = get_completion_page_data()
print('Total students:', data['kpis']['total_students'])
print('Total cohorts:', data['kpis']['total_cohorts'])
print('Average completion rate:', data['kpis']['average_completion_rate'])
print('Male students:', data['kpis']['gender_distribution']['male'])
print('Female students:', data['kpis']['gender_distribution']['female'])
print('Students in table:', len(data['students']))
print('Cohort chart data:', len(data['charts']['cohort_completion']))
print('Programme chart data:', len(data['charts']['programme_completion']))
print('SUCCESS: Completion service working with real data!')

print('\n=== Testing Graduation Service with Real Data ===')
data = get_graduation_page_data()
print('Total graduated students:', data['kpis']['total_graduated_students'])
print('Average completion graduation rate:', data['kpis']['average_completion_graduation_rate'])
print('On-time graduation rate:', data['kpis']['on_time_graduation_rate'])
print('Students in table:', len(data['students']))
print('Programme chart data:', len(data['charts']['programme_graduation_rate']))
print('Cohort chart data:', len(data['charts']['cohort_graduation_rate']))
print('SUCCESS: Graduation service working with real data!')

print('\n=== Testing Filters ===')
print('Testing completion with faculty filter...')
data = get_completion_page_data(faculty='Science')
print('Completion with Science faculty:', data['kpis']['total_students'], 'students')

print('Testing graduation with faculty filter...')
data = get_graduation_page_data(faculty='Science')
print('Graduation with Science faculty:', data['kpis']['total_graduated_students'], 'students')

print('\nAll tests completed successfully!')

from services.completion_service import get_completion_page_data
from services.graduation_services import get_graduation_page_data

print('=== Testing Completion Service ===')
try:
    data = get_completion_page_data()
    print('Total students:', data['kpis']['total_students'])
    print('Total cohorts:', data['kpis']['total_cohorts'])
    print('Average completion rate:', data['kpis']['average_completion_rate'])
    print('Students in table:', len(data['students']))
    print('SUCCESS: Completion service returned data!')
except Exception as e:
    print('ERROR:', e)

print('\n=== Testing Graduation Service ===')
try:
    data = get_graduation_page_data()
    print('Total graduated students:', data['kpis']['total_graduated_students'])
    print('Average completion graduation rate:', data['kpis']['average_completion_graduation_rate'])
    print('On-time graduation rate:', data['kpis']['on_time_graduation_rate'])
    print('Students in table:', len(data['students']))
    print('SUCCESS: Graduation service returned data!')
except Exception as e:
    print('ERROR:', e)

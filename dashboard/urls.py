from django.urls import path

from .academic_levels.views import academic_level_metrics, academic_level_payload, academic_level_view
from .demographics.views import demographic_metrics, demographic_narratives, demographic_payload, demographic_view
from .insights.views import insights_payload, insights_view
from .overview.views import (
    dashboard_home,
    dashboard_home_drilldown,
    dashboard_home_metrics,
    dashboard_home_narratives,
    dashboard_home_payload,
)
from .programmes.views import programme_metrics, programme_narratives, programme_payload, programme_view
from .risk.views import risk_band_drilldown, risk_drilldown_payload, risk_driver_drilldown, risk_level_drilldown, risk_metrics, risk_payload, risk_programme_drilldown, risk_view
from .views import (
    student_detail,
    student_list,
    system_management_view,
)
from .completion.views import (
    completion_view, 
    completion_payload, 
    completion_programmes, 
    completion_faculties, 
    completion_academic_years
)
from .graduation.views import (
    graduation_view, 
    graduation_payload, 
    graduation_programmes, 
    graduation_faculties
)

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("metrics/overview/", dashboard_home_metrics, name="home-metrics"),
    path("metrics/overview/payload/", dashboard_home_payload, name="home-payload"),
    path("metrics/overview/narratives/", dashboard_home_narratives, name="home-narratives"),
    path("metrics/overview/drilldown/", dashboard_home_drilldown, name="home-drilldown"),
    path("students/", student_list, name="students"),
    path("students/<slug:slug>/", student_detail, name="student-detail"),
    path("programme/", programme_view, name="programme"),
    path("metrics/programme/", programme_metrics, name="programme-metrics"),
    path("metrics/programme/payload/", programme_payload, name="programme-payload"),
    path("metrics/programme/narratives/", programme_narratives, name="programme-narratives"),
    path("demographic/", demographic_view, name="demographic"),
    path("metrics/demographic/", demographic_metrics, name="demographic-metrics"),
    path("metrics/demographic/payload/", demographic_payload, name="demographic-payload"),
    path("metrics/demographic/narratives/", demographic_narratives, name="demographic-narratives"),
    path("academic-level/", academic_level_view, name="academic-level"),
    path("metrics/academic-level/", academic_level_metrics, name="academic-level-metrics"),
    path("metrics/academic-level/payload/", academic_level_payload, name="academic-level-payload"),
    path("risk/", risk_view, name="risk"),
    path("risk/band/<str:risk_band>/", risk_band_drilldown, name="risk-band-drilldown"),
    path("risk/level/<str:academic_level>/", risk_level_drilldown, name="risk-level-drilldown"),
    path("risk/driver/<str:risk_driver>/", risk_driver_drilldown, name="risk-driver-drilldown"),
    path("risk/programme/<str:programme>/", risk_programme_drilldown, name="risk-programme-drilldown"),
    path("metrics/risk/", risk_metrics, name="risk-metrics"),
    path("metrics/risk/payload/", risk_payload, name="risk-payload"),
    path("metrics/risk/drilldown/", risk_drilldown_payload, name="risk-drilldown"),
    path("insights/", insights_view, name="insights"),
    path("metrics/insights/payload/", insights_payload, name="insights-payload"),
    path("completion/", completion_view, name="completion"),
    path("metrics/completion/payload/", completion_payload, name="completion-payload"),
    path("api/completion/programmes", completion_programmes, name="completion-programmes"),
    path("api/completion/faculties", completion_faculties, name="completion-faculties"),
    path("api/completion/academic-years", completion_academic_years, name="completion-academic-years"),
    path("graduation/", graduation_view, name="graduation"),
    path("metrics/graduation/payload/", graduation_payload, name="graduation-payload"),
    path("api/graduation/programmes", graduation_programmes, name="graduation-programmes"),
    path("api/graduation/faculties", graduation_faculties, name="graduation-faculties"),
    path("system-management/", system_management_view, name="system-management"),
]

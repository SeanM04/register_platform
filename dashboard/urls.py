from django.urls import path, include

from .academic_levels.views import academic_level_drilldown, academic_level_metrics, academic_level_payload, academic_level_view
from .demographics.views import demographic_drilldown, demographic_metrics, demographic_narratives, demographic_payload, demographic_view
from .insights.views import insights_drilldown_payload, insights_metrics, insights_payload, insights_view
from .overview.views import (
    dashboard_home,
    dashboard_home_drilldown,
    dashboard_home_metrics,
    dashboard_home_narratives,
    dashboard_home_payload,
)
from .programmes.views import programme_drilldown, programme_metrics, programme_narratives, programme_payload, programme_view
from .risk.views import risk_band_drilldown, risk_drilldown_payload, risk_driver_drilldown, risk_level_drilldown, risk_metrics, risk_payload, risk_programme_drilldown, risk_view
from .views import (
    student_detail,
    student_list,
    student_transcript,
    system_management_view,
)
from .reports.views import reports_export_csv, reports_generate, reports_periods_by_year, reports_view
from .completion.views import (
    completion_view,
    completion_metrics,
    completion_payload,
    completion_narratives,
    completion_programmes,
    completion_faculties,
    completion_academic_years,
    completion_periods,
    completion_periods_by_year,
    completion_drilldown
)
from .graduation.views import (
    graduation_view, 
    graduation_payload, 
    graduation_narratives,
    graduation_programmes,
    graduation_faculties,
    graduation_drilldown
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
    path("students/<slug:slug>/transcript/", student_transcript, name="student-transcript"),
    path("programme/", programme_view, name="programme"),
    path("metrics/programme/", programme_metrics, name="programme-metrics"),
    path("metrics/programme/payload/", programme_payload, name="programme-payload"),
    path("metrics/programme/narratives/", programme_narratives, name="programme-narratives"),
    path("metrics/programme/drilldown/", programme_drilldown, name="programme-drilldown"),
    path("demographic/", demographic_view, name="demographic"),
    path("metrics/demographic/", demographic_metrics, name="demographic-metrics"),
    path("metrics/demographic/payload/", demographic_payload, name="demographic-payload"),
    path("metrics/demographic/narratives/", demographic_narratives, name="demographic-narratives"),
    path("metrics/demographic/drilldown/", demographic_drilldown, name="demographic-drilldown"),
    path("academic-level/", academic_level_view, name="academic-level"),
    path("metrics/academic-level/", academic_level_metrics, name="academic-level-metrics"),
    path("metrics/academic-level/payload/", academic_level_payload, name="academic-level-payload"),
    path("metrics/academic-level/drilldown/", academic_level_drilldown, name="academic-level-drilldown"),
    path("risk/", risk_view, name="risk"),
    path("risk/band/<str:risk_band>/", risk_band_drilldown, name="risk-band-drilldown"),
    path("risk/level/<str:academic_level>/", risk_level_drilldown, name="risk-level-drilldown"),
    path("risk/driver/<str:risk_driver>/", risk_driver_drilldown, name="risk-driver-drilldown"),
    path("risk/programme/<str:programme>/", risk_programme_drilldown, name="risk-programme-drilldown"),
    path("metrics/risk/", risk_metrics, name="risk-metrics"),
    path("metrics/risk/payload/", risk_payload, name="risk-payload"),
    path("metrics/risk/drilldown/", risk_drilldown_payload, name="risk-drilldown"),
    path("insights/", insights_view, name="insights"),
    path("metrics/insights/", insights_metrics, name="insights-metrics"),
    path("metrics/insights/payload/", insights_payload, name="insights-payload"),
    path("metrics/insights/drilldown/", insights_drilldown_payload, name="insights-drilldown"),
    path("completion/", completion_view, name="completion"),
    path("metrics/completion/", completion_metrics, name="completion-metrics"),
    path("metrics/completion/payload/", completion_payload, name="completion-payload"),
    path("metrics/completion/narratives/", completion_narratives, name="completion-narratives"),
    path("metrics/completion/drilldown/", completion_drilldown, name="completion-drilldown"),
    path("api/completion/programmes", completion_programmes, name="completion-programmes"),
    path("api/completion/faculties", completion_faculties, name="completion-faculties"),
    path("api/completion/academic-years", completion_academic_years, name="completion-academic-years"),
    path("api/completion/periods", completion_periods, name="completion-periods"),
    path("api/completion/periods-by-year", completion_periods_by_year, name="completion-periods-by-year"),
    path("graduation/", graduation_view, name="graduation"),
    path("metrics/graduation/payload/", graduation_payload, name="graduation-payload"),
    path("metrics/graduation/narratives/", graduation_narratives, name="graduation-narratives"),
    path("metrics/graduation/drilldown/", graduation_drilldown, name="graduation-drilldown"),
    path("api/graduation/programmes", graduation_programmes, name="graduation-programmes"),
    path("api/graduation/faculties", graduation_faculties, name="graduation-faculties"),
    path("reports/", reports_view, name="reports"),
    path("metrics/reports/generate/", reports_generate, name="reports-generate"),
    path("metrics/reports/export/", reports_export_csv, name="reports-export"),
    path("api/reports/periods-by-year/", reports_periods_by_year, name="reports-periods-by-year"),
    path("system-management/", system_management_view, name="system-management"),
    
    # Age API endpoints
    path("api/age/", include("dashboard.api.urls")),
]

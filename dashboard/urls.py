from django.urls import path

from .academic_levels.views import academic_level_metrics, academic_level_view
from .demographics.views import demographic_metrics, demographic_narratives, demographic_payload, demographic_view
from .insights.views import insights_view
from .overview.views import dashboard_home, dashboard_home_metrics, dashboard_home_narratives, dashboard_home_payload
from .programmes.views import programme_metrics, programme_narratives, programme_payload, programme_view
from .risk.views import risk_metrics, risk_view
from .views import (
    student_detail,
    student_list,
    system_management_view,
)

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("metrics/overview/", dashboard_home_metrics, name="home-metrics"),
    path("metrics/overview/payload/", dashboard_home_payload, name="home-payload"),
    path("metrics/overview/narratives/", dashboard_home_narratives, name="home-narratives"),
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
    path("risk/", risk_view, name="risk"),
    path("metrics/risk/", risk_metrics, name="risk-metrics"),
    path("insights/", insights_view, name="insights"),
    path("system-management/", system_management_view, name="system-management"),
]

# Insights Page

Route: `/insights/`

Sidebar label: `Insights`

Primary audience: institutional leaders who need a cross-page watchlist,
recommendations, and operational summary.

## What This Page Does

The Insights page is the platform's monitoring workspace. It combines signals
from risk, registration load, retention, faculty concentration, and intervention
needs into an executive summary.

For non-technical users, this page answers:

- How much student support pressure is visible right now?
- Which faculty or trigger is driving the watchlist?
- What action should teams consider next?
- Which students need attention under the current filter?
- How do I move through the full attention queue 10 students at a time?

For technical users, the page uses a two-phase load. The initial shell renders
immediately. `/metrics/insights/` returns KPI card values within ~50ms using DB
aggregates. `/metrics/insights/payload/` then supplies the final chart rows,
student table, recommendation content, and narrative state.

## Page Architecture

```mermaid
flowchart TD
    A[GET /insights/] --> B[insights_view]
    B --> C[insights.html shell]
    C --> D[insights JS modules]
    D --> E[GET /metrics/insights/]
    D --> F[GET /metrics/insights/payload/]
    E --> G[Fast KPI cards ~50ms]
    F --> H[Insights service - full build]
    H --> I[Risk profiles]
    H --> J[Faculty pressure]
    H --> K[Driver and intervention summaries]
    I --> L[Charts, student table, recommendations]
    J --> L
    K --> L
```

## Main Files

| Layer | Files |
| --- | --- |
| URL routes | `dashboard/urls.py` |
| Views | `dashboard/insights/views.py` |
| Data services | `dashboard/insights/services.py` |
| AI narratives | `dashboard/insights/ai_insights.py` |
| Presenters | `dashboard/insights/presenters.py` |
| Template | `dashboard/templates/dashboard/insights.html` |
| JavaScript | `dashboard/static/dashboard/js/insights/index.js`, `dashboard/static/dashboard/js/insights/` |
| Tests | `dashboard/insights/tests.py` |

## Endpoints

| Route | Function | Purpose |
| --- | --- | --- |
| `GET /insights/` | `insights_view` | Render HTML shell |
| `GET /metrics/insights/` | `insights_metrics` | Fast KPI cards via DB aggregates |
| `GET /metrics/insights/payload/` | `insights_payload` | Full chart rows, flagged students, recommendations |
| `GET /metrics/insights/drilldown/` | `insights_drilldown_payload` | Paginated student rows for chart clicks |

## Performance Notes

- The full payload build calls `build_student_risk_profiles_from_request_and_registrations`, which shares a single `get_filtered_registrations` fetch with the faculty load calculation. Earlier versions fetched registrations twice.
- Cache TTL is 300 seconds. Fast metrics and full payload results are cached under separate keys derived from the active filter scope.
- The fast metrics endpoint uses DB-level `Avg` and `Count` aggregates with simplified risk scoring (marks and fail count only, excluding carried modules and decisions). The numbers are directionally correct for immediate display and are replaced by exact values when the full payload arrives.

## Data Inputs

- Risk profiles from `dashboard/risk/services.py`.
- Registrations filtered by year, period, and faculty.
- Course results and carried-module counts.
- Programme and faculty grouping.

## User Experience Notes

- KPI helper text should update after payload hydration and should not stay in
  loading copy once real data has arrived.
- The primary takeaway should be written as an action-oriented summary.
- The student table should match the same filter scope shown in the topbar.
- `Students Needing Attention` now uses the full flagged-student list from the
  payload instead of a short preview.
- The attention queue is paginated at `10` students per page with page-level
  `Prev` and `Next` controls.
- In `Intervention Summary`, a single failed module and a single carried module
  are treated as the same driver and displayed as `1 carried module`.

## Maintenance Checklist

- Keep presenter placeholder copy and payload hydration copy aligned.
- Run `python manage.py test dashboard.insights.tests` after insight payload or
  narrative changes.

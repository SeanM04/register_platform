# Documentation Index

This folder contains implementation notes and operational guidance for the registrar analytics platform.

## Quick Navigation

### User-Facing And Deployment

- [DEPLOYMENT.md](DEPLOYMENT.md)
  Deployment checklist, database setup, and release preparation
- [OPERATIONS.md](OPERATIONS.md)
  Monitoring, troubleshooting, and day-to-day support tasks

### Architecture And Feature Design

- [ARCHITECTURE.md](ARCHITECTURE.md)
  Django app structure, models, and platform design notes
- [AI_INSIGHTS.md](AI_INSIGHTS.md)
  Shared AI narrative generation patterns across dashboards
- [STUDENT_HISTORY.md](STUDENT_HISTORY.md)
  Student timeline grouping, repeat-attempt handling, visiting-stage caps, latest-first detail tabs, and transcript helper logic
- [CHATBOT.md](CHATBOT.md)
  UniStudio chatbot widget — async SSE streaming, real-time status feedback, 20-handler dispatch, rate limiting, and provider fallback
- [DASHBOARD_HOME.md](DASHBOARD_HOME.md)
  Landing dashboard layout, filter bar, and drill-down behavior
- [COMPLETION_ANALYTICS.md](COMPLETION_ANALYTICS.md)
  Completion rules, effective cohorts, narratives, and frontend wiring
- [GRADUATION_ANALYTICS.md](GRADUATION_ANALYTICS.md)
  Graduation rules, visiting/engineering stage mapping, eligible-denominator KPIs, payload performance notes, and frontend wiring
- [pages/students.md](pages/students.md)
  Student detail display rules, latest-first year tabs, repeat-semester grouping, and profile behavior
- [pages/demographics.md](pages/demographics.md)
  Demographic charts, cohort-aware year distribution, and map behavior

### Performance And Drill-Downs

- [DRILLDOWN_OPTIMIZATION.md](DRILLDOWN_OPTIMIZATION.md)
  Backend drill-down performance strategy and caching
- [DRILLDOWN_FRONTEND.md](DRILLDOWN_FRONTEND.md)
  Frontend drill-down rendering, pagination, and interactions

## Feature Guides

### Sidebar Page Guides

Folder: `docs/pages/`

Covers every sidebar destination:

- [Dashboard](DASHBOARD_HOME.md)
- [Students](pages/students.md)
- [Programmes](pages/programmes.md)
- [Demographics](pages/demographics.md)
- [Academic Levels](pages/academic-levels.md)
- [Completion Analysis](COMPLETION_ANALYTICS.md)
- [Graduation Analysis](GRADUATION_ANALYTICS.md)
- [Risk Analysis](pages/risk-analysis.md)
- [Insights](pages/insights.md)
- [System Management](pages/system-management.md)

Shared sidebar pattern:

- each page starts from a Django route
- the route renders a page shell template
- optional metrics, payload, or narratives endpoints hydrate charts and tables
- page-scoped JavaScript turns the payload into the visible UI

Shared sidebar data model:

- `Faculty -> Department -> Programme -> Registration`
- `Student -> Registration`
- `AcademicPeriod -> Registration`
- `Registration -> CourseResult -> Course`

### Landing Dashboard

File: [DASHBOARD_HOME.md](DASHBOARD_HOME.md)

Covers:

- shared year, period, and faculty filters
- outcomes and risk charts
- drill-down flow and pagination
- narrative helper patterns
- files to touch when adding a new home chart

### AI Insights

File: [AI_INSIGHTS.md](AI_INSIGHTS.md)

Covers:

- provider selection and fallback behavior
- rule-based narratives
- OpenAI integration
- response normalization and diagnostics

### Completion Analytics

File: [COMPLETION_ANALYTICS.md](COMPLETION_ANALYTICS.md)

Covers:

- documented completion and zero-completion rules
- effective cohort shifting logic
- cumulative cohort-timeline heatmap behavior
- completion payload and narratives endpoints
- completion details table pagination at `10` rows with a sticky header
- frontend chart rendering and chart footer badge states
- troubleshooting for stale routes, missing endpoints, and fallback guidance

### Reports

File: `dashboard/reports/views.py`

Current note:

- report `%` outputs are rounded to whole numbers before they reach the page
- report `Avg Mark` values are also rounded to whole numbers for display

### Risk And Insights Table Notes

Current note:

- the Risk `Action Register` now paginates at `10` rows per page
- `Insights -> Students Needing Attention` now shows the full flagged queue in
  `10`-row pages with `Prev` and `Next`

### Graduation Analytics

File: [GRADUATION_ANALYTICS.md](GRADUATION_ANALYTICS.md)

Covers:

- documented graduation-stage rules by programme family
- effective cohort use and on-time graduation logic
- graduation payload and narratives endpoints
- frontend ECharts rendering and chart footer badge states
- troubleshooting for stale routes, missing endpoints, and fallback guidance

## Common Maintenance Tasks

### Add Or Update A Dashboard Feature

1. Update the backend view or service
2. Update the template and frontend module
3. Add or adjust tests
4. Update the relevant document in this folder

### Investigate Narrative Issues

1. Check the page payload endpoint
2. Check the narratives endpoint
3. Confirm provider settings in the environment
4. Review the diagnostics banner and browser console
5. Restart the dev server if a newly added route is missing

### Validate Changes

```powershell
python manage.py check
python manage.py test
```

## Documentation Structure

```text
docs/
|-- README.md
|-- ARCHITECTURE.md
|-- AI_INSIGHTS.md
|-- DASHBOARD_HOME.md
|-- pages/
|   |-- README.md
|   |-- students.md
|   |-- programmes.md
|   |-- demographics.md
|   |-- academic-levels.md
|   |-- risk-analysis.md
|   |-- insights.md
|   `-- system-management.md
|-- COMPLETION_ANALYTICS.md
|-- GRADUATION_ANALYTICS.md
|-- DRILLDOWN_OPTIMIZATION.md
|-- DRILLDOWN_FRONTEND.md
|-- DEPLOYMENT.md
`-- OPERATIONS.md
```

## Updating Documentation

When you change platform behavior:

- update the nearest feature document
- add new routes or files to the relevant guide
- document fallback or troubleshooting behavior when it affects operators
- keep root `README.md` links in sync with this index

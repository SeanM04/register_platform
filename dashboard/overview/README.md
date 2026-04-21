## Overview Dashboard

This feature package owns the landing page users see immediately after login.

### What it does

- builds the top summary cards
- shapes the story-first chart data for cohort outcomes, risk mix, faculty load, and progress status
- creates the quick-route action cards that send users into the deeper analytics pages

### Why it exists

The old home page was only a metric wall with placeholder charts. This package keeps the landing page maintainable by separating:

- `services.py`: data shaping and landing-page recommendations
- `ai_insights.py`: safe rule-based and optional AI-assisted overview narratives
- `presenters.py`: template context assembly
- `views.py`: HTTP entrypoints for the page and metric hydration

### Data sources

The overview dashboard works from the same filtered registration scope used across the rest of the platform. It reuses:

- filtered registrations from `dashboard.views.get_filtered_registrations()`
- risk profiling from `dashboard.risk.services.build_student_risk_profiles()`
- course results for assessment-outcome summaries

### Landing-page intent

This page should answer three questions quickly:

1. How healthy is the visible cohort right now?
2. Where is the load or pressure concentrating?
3. Which specialist page should the user open next?

### AI overview narratives

The landing page now follows the same safe overview-narrative pattern used on the
specialist tabs:

- deterministic rules are always built first
- Gemini or OpenAI can optionally rewrite the four chart-card narratives
- the hero banner and route cards stay deterministic

The AI-backed card keys are:

- `outcomes`
- `risk`
- `faculty`
- `progress`

### Drill-Down Data Endpoint

The landing page supports on-demand student drill-downs from chart clicks via the `dashboard:home-drilldown` endpoint.

**Parameters:**
- `chart`: `outcomes` or `risk_distribution`
- `bucket`: outcome status (`passed`, `failed`, `awaiting`) or risk band (`critical`, `high`, `medium`, `low`)
- `page`: page number (default 1)
- `page_size`: rows per page (default 100, max 100)

**Response includes:**
- `title`, `subtitle`: drill-down context
- `columns`: minimal field list (name, registration_number, programme)
- `rows`: paginated student records with detail_url
- `page`, `page_size`, `page_count`, `total_count`: pagination metadata

**Drill-Down Optimizations:**
- Minimal Payload: Only three columns returned to reduce JSON size
- Server-Side Pagination: Database-level OFFSET/LIMIT for efficient row slicing
- Caching: 30-second TTL per filter scope, chart, bucket, page, and page_size

**Implementation:**
- Backend: `build_overview_drilldown_data()`, `_build_outcome_drilldown_payload()`, `_build_risk_drilldown_payload()`
- Cache management: `bust_overview_drilldown_cache_for_request()`
- Frontend: `drilldown.js`, `drilldown_modal.js`

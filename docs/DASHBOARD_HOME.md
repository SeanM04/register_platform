# Landing Dashboard

This document explains the current structure of the landing dashboard shown at
`dashboard:home`.

## Route And Audience

Route: `/`

Sidebar label: `Dashboard`

Primary audience: administrators and academic leaders monitoring institution-wide
outcomes, risk distribution, faculty load, and high-level progression signals.

## What This Page Does

The landing dashboard is the shared institutional overview page. It combines
headline KPIs, outcome and risk charts, faculty-level comparisons, and drilldown
entry points that lead users into filtered student lists.

For non-technical users, this page answers:

- What is happening across the institution right now?
- Which outcome or risk buckets need attention first?
- Which faculties carry the heaviest visible load?
- Which chart slice should I drill into to see the affected students?

## 1. Why The Page Is Split

The landing dashboard now uses a shell-plus-hydration flow so the first paint is
fast even when the filtered registration dataset is large.

The page is intentionally split into three layers:

- shell HTML from `dashboard_home()`
- chart and action-card payload from `dashboard_home_payload()`
- optional overview narratives from `dashboard_home_narratives()`

That separation keeps the page responsive while still allowing the heavier
overview calculations and AI-assisted copy to arrive after the shell is visible.

## 2. Backend Endpoints

- `dashboard/overview/views.py`
  Owns the landing dashboard endpoints.
- `dashboard_home()`
  Renders `dashboard/templates/dashboard/home.html` with lightweight summary-card
  placeholders and the shared layout context.
- `dashboard_home_metrics()`
  Returns the same headline KPI values used by the overview payload so the
  homepage cards and AJAX hydration stay in sync.
- `dashboard_home_payload()`
  Returns the heavier chart datasets and route cards. Backed by
  `get_cached_overview_dashboard_data()` with a 5-minute TTL. Cold rebuilds
  take ~3–4 s after the N+1 fix described in section 10.
- `dashboard_home_narratives()`
  Returns the optional AI or rule-based chart-card narratives separately from the
  chart data.

## 3. Service Layer

- `dashboard/overview/services.py`
  Builds the filtered overview payload from registrations, results, and derived
  risk profiles.
- `get_cached_overview_dashboard_data()`
  Caches the assembled overview payload per filter scope (5-minute TTL).
- `build_overview_dashboard_data()`
  Produces:
  - `summary_metrics`
  - `summary_cards`
  - `outcome_rows`
  - `risk_distribution_rows`
  - `faculty_load_rows`
  - `progress_rows`
  - `action_cards`
- `dashboard/views.py` → `get_home_summary_values()`
  Compatibility wrapper used by `dashboard_home_metrics()`. Delegates to the
  overview feature package so the shared KPI set stays aligned across entry
  points.

## 4. Frontend Modules

- `dashboard/static/dashboard/js/home.js`
  Waits for shared chart libraries, wires chapter toggles, and boots the page.
- `dashboard/static/dashboard/js/home/index.js`
  Orchestrates the async shell, payload hydration, narrative updates, and chart
  resize handling.
- `dashboard/static/dashboard/js/home/context.js`
  Stores the shared data, DOM references, and UI flags used across the home page.
- `dashboard/static/dashboard/js/home/narratives.js`
  Applies local fallback narratives, AI badges, loading badges, and footer
  guidance states.
- `dashboard/static/dashboard/js/home/outcomes.js`
  Builds the outcome donut.
- `dashboard/static/dashboard/js/home/risk_distribution.js`
  Builds the risk-distribution chart.
- `dashboard/static/dashboard/js/home/faculty_load.js`
  Builds the faculty-load bar chart.
- `dashboard/static/dashboard/js/home/progress.js`
  Builds the registration-decision chart.

## 5. Narrative States

Each chart card now supports three visible narrative states:

- `AI loading`
  The optional provider request has started, but the response is still pending.
- `AI`
  The card is showing provider-generated copy with normalized severity and
  confidence.
- `Guidance`
  The card is showing deterministic rule-based copy because AI is disabled,
  unavailable, or the request fell back.

The chapter summaries use the same narrative payload, but only show the AI badge
when the final response source is actually AI.

## 6. Fact-Pack And AI Flow

The landing dashboard AI helper lives in `dashboard/overview/ai_insights.py`.

Important implementation details:

- deterministic fallback narratives are always built first
- the overview fact pack is intentionally compact for the broad `All / All / All`
  filter scope
- successful AI responses are cached per normalized fact pack
- provider failures fall back safely to deterministic guidance copy

## 7. Chart Drill-Downs

Users can click on chart slices or bars to drill into filtered student lists.

Drill-down requests are handled by:

- `dashboard_home_drilldown()` endpoint in `dashboard/overview/views.py`
- `build_overview_drilldown_data()` in `dashboard/overview/services.py`
- Client-side drill-down modal in `dashboard/static/dashboard/js/home/drilldown.js` and `drilldown_modal.js`

### Drilldown Performance Optimization

The drill-down feature includes three key performance optimizations:

#### 1. Minimal Payload

- Only three columns returned: `Student`, `Student Number`, `Programme`
- Extra metadata stripped from response to reduce JSON size
- Outcome and risk drill-downs use identical lightweight row format

#### 2. Server-Side Pagination

- Default: 100 rows per page
- Maximum: 100 rows per page (MAX_DRILLDOWN_PAGE_SIZE)
- Query applies `OFFSET` and `LIMIT` at the database level
- Frontend requests specific pages on user navigation

#### 3. Short-Lived Caching

- Cache TTL: 30 seconds (OVERVIEW_CACHE_TTL_SECONDS)
- Cache key includes: filter scope, chart, bucket, page, page_size
- Manual cache bust available via `bust_overview_drilldown_cache_for_request()`
- Prevents repeated queries for the same drill-down slice within a session

### Drill-Down Data Flow

1. User clicks a chart slice or bar
2. JavaScript captures the chart key (`outcomes` or `risk_distribution`) and bucket key
3. Browser requests `dashboard:home-drilldown` with `?chart={chart_key}&bucket={bucket_key}&page=1&page_size=100`
4. Backend checks cache; if miss, builds outcome or risk profiles
5. Backend filters to matching bucket and returns paginated rows
6. Modal renders table with 100 rows and Prev/Next navigation
7. User pagination triggers new requests with updated `page` parameter
8. Fresh cache entries are created for each page

## 8. Shared Filter Bar

The page still uses the shared filter bar from `templates/base.html` and
`dashboard/static/dashboard/css/base.css`.

Important behavior:

- filter changes still submit through the shared topbar form
- the current filter query string is forwarded to async endpoints in the browser
- sidebar navigation preserves the active filter scope in generated links

## 9. Files To Update Together

If you add, rename, or remove a landing-page chart card, update these together:

- `dashboard/overview/services.py`
- `dashboard/overview/ai_insights.py`
- `dashboard/templates/dashboard/home.html`
- `dashboard/static/dashboard/js/home/context.js`
- `dashboard/static/dashboard/js/home/narratives.js`
- the relevant chart module in `dashboard/static/dashboard/js/home/`
- `dashboard/overview/tests.py`

## 10. Performance Fixes (2026-06-01)

### Problem: KPI Cards Stuck in Loading State

The metrics and payload endpoints both called `get_cached_overview_dashboard_data()`.
On every 5-minute cache expiry, a cold rebuild was triggered that blocked both
endpoints for up to 71 seconds, leaving KPI cards in their skeleton loading state
until the rebuild finished (or until the browser gave up).

### Fix 1 — Keep KPI Values Consistent

`dashboard_home_metrics()` now uses the same overview summary metrics as the
payload endpoint, which keeps the headline cards aligned across the shell and
hydration flow.

The payload endpoint continues to use `get_cached_overview_dashboard_data()` for
the full chart and card dataset.

### Fix 2 — N+1 Query Explosion in Risk Profile Build

**Root cause**: `build_student_risk_profiles_from_registrations()` in
`dashboard/risk/services.py` called `build_registration_display_level_index()`
when no pre-built index was supplied. That function called
`build_student_timeline()` per student, which accessed
`registration.attendance_type_record` — a relation absent from the queryset's
`select_related` — causing one extra DB query per registration.

With 6 389 registrations this produced 9 000+ queries and 68 of the 71-second
cold rebuild time.

**Fix**:

- Changed the guard in `build_student_risk_profiles_from_registrations()` from
  `registration_level_index or build_registration_display_level_index(...)` to an
  explicit `if registration_level_index is None` check, so an empty dict `{}`
  correctly bypasses the build.
- `build_overview_dashboard_data()` now passes `registration_level_index={}` when
  calling the risk profiler. The overview only needs risk scores and band labels,
  not the detailed academic-level display metadata. The fallback path in
  `build_student_risk_profiles_from_registrations()` uses
  `extract_registration_year_semester()` (pure Python, zero DB queries) to derive
  a generic level label.

**Result**: Cold-cache full dashboard build went from **71 s → 3.6 s**. Risk
distribution rows and at-risk counts are unchanged.

### Chart Border Radius

Rounded top corners (`borderRadius: [6, 6, 0, 0]`) were added to the bar
`itemStyle` in:

- `dashboard/static/dashboard/js/home/risk_distribution.js`
- `dashboard/static/dashboard/js/home/progress.js`

Rounded right-end corners (`borderRadius: [0, 6, 6, 0]`) were added to:

- `dashboard/static/dashboard/js/home/faculty_load.js`

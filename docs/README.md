# Documentation Index

This folder contains comprehensive documentation for the Registrar Platform landing dashboard and backend systems.

## Quick Navigation

### User-Facing & Deployment

- [**DEPLOYMENT.md**](DEPLOYMENT.md) – Deployment checklist, database setup, initial data import
- [**OPERATIONS.md**](OPERATIONS.md) – Monitoring, troubleshooting, common operations

### Architecture & Design

- [**ARCHITECTURE.md**](ARCHITECTURE.md) – System architecture, database schema, core modules
- [**AI_INSIGHTS.md**](AI_INSIGHTS.md) – AI-powered narrative generation for dashboard cards
- [**DASHBOARD_HOME.md**](DASHBOARD_HOME.md) – Landing dashboard layout, filter bar, chart interactions

### Drill-Down Features (Pagination & Optimization)

- [**DRILLDOWN_OPTIMIZATION.md**](DRILLDOWN_OPTIMIZATION.md) – **START HERE** for drill-down overview
  - Problem statement and optimization strategy
  - Minimal payload design (3-column rows)
  - Server-side pagination (100 rows/page)
  - 30-second TTL caching
  - Performance metrics (10–100x improvements)
  - API reference and cache management

- [**DRILLDOWN_FRONTEND.md**](DRILLDOWN_FRONTEND.md) – Frontend drill-down implementation details
  - Modal rendering and pagination UI
  - JavaScript components (drilldown.js, drilldown_modal.js)
  - CSS styling and accessibility
  - Event flow and error handling
  - Testing considerations

## Feature Documentation

### Landing Dashboard

**File**: [DASHBOARD_HOME.md](DASHBOARD_HOME.md)

Covers:
1. Shared filter bar (year, period, faculty)
2. Outcomes chart with drill-down
3. Risk distribution chart with drill-down
4. Narrative AI helper with fallback
5. Data refresh timing and caching
6. Fact pack assembly (test insights)
7. Chart drill-downs (pagination, performance)
8. Shared filter bar behavior
9. Files to update when adding new charts

### AI Insights

**File**: [AI_INSIGHTS.md](AI_INSIGHTS.md)

Covers:
- Narrative generation for each dashboard section
- Fallback narratives and error handling
- OpenAI integration
- Caching of AI responses

### System Architecture

**File**: [ARCHITECTURE.md](ARCHITECTURE.md)

Covers:
- Django app structure
- Database models (Student, Registration, Course, Result)
- User roles and permissions (Admin, Academic Staff, Student)
- Dashboard views and services

## Drill-Down Deep Dive

### Why Drill-Downs Matter

Chart drill-downs allow users to click on:
- **Outcome slices**: `Passed`, `Failed`, `Awaiting Approval`
- **Risk bars**: `Critical`, `High`, `Medium`, `Low`

This opens a modal showing 100 students from that slice, paginated for performance.

### Performance Optimization (Summary)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Cold drill-down** | 2–3 seconds | 150–250ms | 10–20x faster |
| **Repeated drill-down** | 2–3 seconds | 0–10ms | 100–300x faster |
| **Payload size** | 5–15 MB | 5–15 KB | 1000x smaller |
| **Memory usage** | ~50MB+ | ~1KB | ~50,000x less |

### Key Design Decisions

1. **Minimal Payload**: Only `name`, `registration_number`, `programme` + `detail_url`
   - Reduces JSON by ~70%
   - Speeds network transfer
   - Maintains user context

2. **Server-Side Pagination**: OFFSET/LIMIT at database level
   - Only requested 100 rows fetched
   - Constant memory usage
   - ~200ms per page load

3. **Short-Lived Caching**: 30-second TTL per unique request
   - Zero queries for repeated drill-downs within session
   - Unique cache key per filter scope + chart + bucket + page
   - Manual cache bust for admin operations

## Backend Components

### Services

- `dashboard/overview/services.py`
  - `build_overview_drilldown_data()` – Main entry point with caching
  - `_build_overview_drilldown_data()` – Uncached implementation
  - `_build_outcome_drilldown_payload()` – Outcome row builder
  - `_build_risk_drilldown_payload()` – Risk row builder
  - `bust_overview_drilldown_cache_for_request()` – Manual cache bust

### Views

- `dashboard/overview/views.py`
  - `dashboard_home()` – Landing page view
  - `dashboard_home_drilldown()` – Drill-down data endpoint

### Tests

- `dashboard/overview/tests.py` – 18 unit tests covering:
  - Drill-down payload format
  - Pagination metadata
  - Minimal field validation
  - Cache creation and deletion

## Frontend Components

### JavaScript

- `dashboard/static/dashboard/js/home/drilldown.js` – Drill-down request orchestration
- `dashboard/static/dashboard/js/home/drilldown_modal.js` – Modal UI rendering
- `dashboard/static/dashboard/js/home/home.js` – Chart click event handlers

### CSS

- `dashboard/static/dashboard/css/home.css` – Pagination and modal styling

### Templates

- `dashboard/templates/dashboard/home.html` – Landing dashboard HTML

## Common Tasks

### Add a New Chart

1. Create chart module in `dashboard/static/dashboard/js/home/`
2. Add chart class to `dashboard/overview/services.py`
3. Update `dashboard/templates/dashboard/home.html` with chart container
4. Register chart context in `dashboard/static/dashboard/js/home/context.js`
5. Add narratives in `dashboard/overview/ai_insights.py` and `dashboard/static/dashboard/js/home/narratives.js`
6. Add tests to `dashboard/overview/tests.py`
7. Update this documentation with new chart

### Optimize a Query

1. Review query in `dashboard/overview/services.py`
2. Add `.select_related()` or `.prefetch_related()` as needed
3. Consider `.values()` or `.only()` for specific columns
4. Add test case to verify optimization
5. Run `manage.py test dashboard` to validate

### Adjust Cache Behavior

- Change TTL: Update `OVERVIEW_CACHE_TTL_SECONDS` in `dashboard/overview/services.py`
- Disable cache: Remove `cache.get_or_set()` wrapper (for debugging)
- Clear cache manually: Call `bust_overview_drilldown_cache_for_request(request)` or `bust_overview_drilldown_caches()`

### Test Drill-Down Locally

```bash
# Start server
python manage.py runserver

# Navigate to http://localhost:8000/dashboard/home/

# Click a chart slice to see drill-down modal
# Check browser console (F12) for any JS errors
# Check Django debug toolbar for query count
```

## Documentation Structure

```
docs/
  ├── README.md (this file)
  ├── ARCHITECTURE.md         (system design)
  ├── DASHBOARD_HOME.md       (landing page features)
  ├── AI_INSIGHTS.md          (narrative generation)
  ├── DRILLDOWN_OPTIMIZATION.md (drill-down strategy)
  ├── DRILLDOWN_FRONTEND.md   (drill-down UI code)
  ├── DEPLOYMENT.md           (deployment checklist)
  └── OPERATIONS.md           (runtime operations)
```

## Updating Documentation

When you make changes to the codebase:

1. **Code changes**: Update the relevant `.md` file with implementation details
2. **New features**: Create a new `.md` file and add a link to this README
3. **Architecture changes**: Update ARCHITECTURE.md and DASHBOARD_HOME.md
4. **Performance improvements**: Update DRILLDOWN_OPTIMIZATION.md with new metrics

## Support & Questions

For questions about specific features, start with:
1. The corresponding `.md` file listed above
2. Code comments in `dashboard/overview/services.py` and `dashboard/overview/views.py`
3. Test cases in `dashboard/overview/tests.py` for expected behavior
4. The Django debug toolbar for runtime inspection

---

**Last Updated**: 2024
**Drill-Down Optimization**: Complete
**Frontend**: Fully Documented
**Caching**: Production Ready

# Completion Analytics

This document explains the current completion analysis implementation, including the backend rule engine, the page payload assembly, the optional AI narrative flow, and the frontend chart rendering.

## Purpose

The completion page answers four related questions:

- how completion is calculated for each visible student
- how zero-completion decisions shift a student into a later effective cohort
- how cohort and programme completion rates are aggregated for charts
- whether chart-level narrative copy came from an AI provider or from the local rule-based fallback

## Main Routes

- `/completion/`
  Completion Analysis page shell
- `/metrics/completion/payload/`
  Main chart, KPI, and table payload
- `/metrics/completion/narratives/`
  Optional AI or rule-based chart narratives with diagnostics
- `/api/completion/programmes`
  Programme filter options
- `/api/completion/faculties`
  Faculty filter options
- `/api/completion/academic-years`
  Academic year filter options
- `/api/completion/periods`
  Period filter options
- `/api/completion/periods-by-year`
  Period options grouped by extracted year

## Completion Rules

The shared rule helper lives in `services/completion_rules.py`.

### Core constants

- `PASS_MARK = 50.0`
- `MAX_FAILS = 3`

### Zero-completion decisions

The following decisions force `0%` completion for the current semester and shift the next effective cohort:

- `repeat`
- `repeat level`
- `deferred`
- `discontinue`
- `expelled`
- `results nullified`
- `results suppressed`
- `suspended for two semesters`

Most of these shift the effective cohort by `+1` semester. Suspension shifts by `+2`.

### Student completion calculation

`student_completion_percentage()` applies the documented rule order:

1. If the decision matches a zero-completion rule, return `0.0`
2. Remove null marks
3. If no marks remain, return `0.0`
4. Count passed courses using `mark >= 50`
5. If failed courses are `4+`, return `0.0`
6. Otherwise return `(passed / total) * 100`

## Backend Data Flow

The main service lives in `services/completion_service.py`.

### Registration loading

`_get_registration_history()` loads:

- `student`
- `programme -> department -> faculty`
- `period`
- prefetched course-result marks

Optional faculty filtering is applied at the query level.

### Student record construction

`_build_student_records()` walks each student's registrations in period order and builds the derived fields used by the page:

- `completion_rate`
- `zero_completion_reason`
- `effective_cohort_label`
- `original_cohort_label`
- `cumulative_shift`
- `is_shifted`
- `passed_courses`
- `failed_courses`
- progression labels used by the cohort chart

If a registration carries a zero-completion decision, that registration stays at `0%` and the student's future records inherit the cohort shift.

### Cohort completion heatmap logic

The completion heatmap now uses a cumulative cohort-timeline model instead of
raw imported `academic_year` and `semester` labels.

Key principles:

1. **Rows represent visible cohort periods**
   The row label comes from the actual registration period shown by the selected
   completion scope.
2. **Displayed progression is intake-relative**
   A student's first visible registration is treated as `Y1 S1`, the next cohort
   period as `Y1 S2`, then `Y2 S1`, and so on.
3. **Cumulative cohort rows**
   Later cohort rows can contain students at several displayed stages at once,
   which is why one row can show `Y1 S1`, `Y1 S2`, `Y2 S1`, etc.
4. **Topbar cohort filtering uses the actual selected period**
   Selecting a year and period filters the visible registrations first, then the
   heatmap groups those registrations by their actual visible cohort period.
5. **Empty cells stay blank**
   Cells with no students return `None` so the frontend renders a blank tile.

#### Heatmap Data Structure

```python
if profiles:
    completion_rate = round(sum(profile["completion_rate"] for profile in profiles) / len(profiles), 1)
else:
    completion_rate = None
```

Important distinction:

- completion percentage values still keep one decimal place internally
- progression labels use the cohort timeline (`Y1 S1` ... `Y5 S2`)
- the heatmap row itself is still the real visible cohort period label

### Page aggregation

`get_completion_page_data()` returns a dictionary with:

- `kpis`
- `charts`
- `students`

#### KPIs

- `total_students`
- `total_cohorts`
- `average_completion_rate`
- `zero_completion_students`
- `shifted_students`
- `gender_distribution`

#### Charts

- `cohort_completion`
  Average completion by visible cohort period and cumulative progression point.
  The x-axis displays the cohort-timeline stages from `Y1 S1` onward. Cells with
  actual student data show completion rates, while cells without students are
  returned as `null` so the frontend leaves them blank.
- `programme_completion`
  Average completion by programme, plus zero-completion share
- `zero_completion_drivers`
  Count of visible `0%` reasons such as `Repeat shift`, `Failed 4+ courses`, or `No marks recorded`

#### Student table

The table uses each student's latest visible record and shows:

- student identity
- programme
- academic stage
- decision
- effective cohort
- original cohort
- shifted flag
- zero-completion reason
- completion rate

## Views Layer

The page controller lives in `dashboard/completion/views.py`.

### `completion_view()`

Renders the page shell and injects:

- the active navigation key
- the page title
- whether AI narratives are configured to be available

### `completion_payload()`

Calls `get_completion_page_data()` and returns the main JSON payload for the frontend.

### `completion_narratives()`

Calls:

- `get_completion_page_data()`
- `dashboard.completion.ai_insights.get_completion_card_narratives_result()`

This endpoint returns:

- `card_narratives`
- `diagnostics`

## AI Narratives

Completion chart narratives are implemented in `dashboard/completion/ai_insights.py`.

### Cards covered

- `cohort`
- `programme`
- `drivers`

### Fact-pack assembly

`build_completion_fact_pack()` reduces the page payload into a smaller structured summary for narrative generation. It captures:

- page-level KPIs
- strongest and weakest cohort rows
- strongest and weakest programme rows
- dominant zero-completion driver

### Rule-based fallback

`build_rule_based_completion_narratives()` always provides deterministic copy when:

- AI is disabled
- provider mode is `rules`
- Google or OpenAI fails
- the provider returns invalid JSON or incomplete fields

### Provider flow

`get_completion_card_narratives_result()` attempts:

1. Google Gemini, when configured and allowed
2. OpenAI, when configured and allowed
3. local rule-based fallback

The response includes diagnostics such as:

- configured provider
- provider attempted
- returned source
- status
- fallback reason
- fallback detail

## Frontend Files

### Template

`dashboard/templates/dashboard/completion.html`

Responsibilities:

- chart containers
- KPI cards
- student table shell
- story banner
- chart-note footer slots
- payload and narratives endpoint wiring through `data-*` attributes

### JavaScript

`dashboard/static/dashboard/js/completion.js`

Responsibilities:

- fetch the completion payload
- render KPI values
- render ECharts charts
- render the student table and CSV export
- fetch optional narratives
- show a visible diagnostics banner for loading, AI success, fallback, or endpoint failure
- render chart-footer badges as either `AI` or `Guidance`
- handle cohort completion heatmap with complete x-axis and blank cells for missing data

#### Heatmap Implementation

The cohort completion heatmap uses ECharts with special configuration:

```javascript
// Visual map with null value handling
visualMap: {
    type: "piecewise",
    pieces: [
        { value: null, label: "No data", color: "#f1f5f9" },  // Blank cells
        { min: 0, max: 49, label: "0% - 49%", color: "#dc2626" },
        { min: 50, max: 74, label: "50% - 74%", color: "#f59e0b" },
        { min: 75, max: 100, label: "75% - 100%", color: "#16a34a" },
    ]
}

// Tooltip handling for null values
formatter: (params) => {
    const completionRate = params.data.completionRate;
    const completionText = completionRate === null ? "No data" : `${Math.round(completionRate)}%`;
    // ... rest of tooltip logic
}
```

### CSS

`dashboard/static/dashboard/css/completion.css`

Responsibilities:

- completion page layout
- KPI cards
- story banner
- chart note/footer styling
- AI and guidance pill styling
- diagnostics status styling
- table styling

## Chart Notes and Diagnostics

The completion page uses two related but different signals:

### Chart footer badge

Rendered in the chart note row:

- `AI` when the narrative payload returned `status = "ai"` from Google or OpenAI
- `Guidance` when the page is using rule-based fallback copy

### Diagnostics banner

Rendered near the story banner:

- `loading` while the narratives request is in flight
- `ai` when a provider generated the narratives
- `rules` or `fallback` when local copy is being used
- `error` when the endpoint URL is missing or the request failed

This separation is important: the chart note explains the current card's narrative mode, while the diagnostics banner explains what happened at the provider or endpoint level.

## Local Development Notes

If the completion page shows local guidance instead of AI copy during development, check these first:

1. Confirm `/metrics/completion/narratives/` exists in `dashboard/urls.py`
2. Restart `python manage.py runserver` after adding or renaming the route
3. Hard-refresh the browser so the latest `completion.js` bundle is loaded
4. Check the diagnostics banner on the page for timeout, missing endpoint, or fallback messages

If the page shows a missing narratives endpoint error, the dev server is usually running an older URL map and needs a restart.

## Heatmap Debugging and Development

### Debugging Commands

Several management commands are available for heatmap debugging:

- `python manage.py debug_heatmap_zeros` - Shows how completion rates are calculated and verifies null vs zero values
- `python manage.py show_heatmap_calculation` - Demonstrates the completion rate calculation process with sample data
- `python manage.py count_y1s1_2025` - Counts students in specific progression levels and periods
- `python manage.py check_available_years` - Lists all academic years with data distribution
- `python manage.py find_cohort_218` - Shows cohort structure and academic year relationships

### Common Issues and Solutions

1. **Zeros appearing instead of blank spaces**:
   - Backend: Ensure `completion_rate = None` for empty cells
   - Frontend: Verify visualMap includes `{ value: null, label: "No data", color: "#f1f5f9" }`
   - Tooltip: Check null handling in formatter function

2. **Missing progression levels on x-axis**:
   - Verify `_get_all_progression_levels()` returns all 10 levels (Y1 S1 to Y5 S2)
   - Check that `combined_progression_levels = all_progression_levels` is used

3. **Inconsistent cohort tracking**:
   - Ensure grouping uses `original_cohort_label` not `effective_cohort_label`
   - Verify students appear only once in aggregations

## Tests

`dashboard/completion/tests.py` covers:

- payload shape
- filter option endpoints
- zero-completion decision shifts
- four-failed-course zero-completion behavior
- rule-based narratives
- OpenAI narrative normalization
- heatmap data structure and null value handling

Recommended checks after changing completion code:

```powershell
python manage.py test dashboard.completion.tests
python manage.py check
python manage.py debug_heatmap_zeros  # Verify heatmap behavior
```

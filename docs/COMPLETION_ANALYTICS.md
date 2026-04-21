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
  Average completion by effective cohort and progression point
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

## Tests

`dashboard/completion/tests.py` covers:

- payload shape
- filter option endpoints
- zero-completion decision shifts
- four-failed-course zero-completion behavior
- rule-based narratives
- OpenAI narrative normalization

Recommended checks after changing completion code:

```powershell
python manage.py test dashboard.completion.tests
python manage.py check
```

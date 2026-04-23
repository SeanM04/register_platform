# Graduation Analytics

This document explains the current graduation analysis implementation, including the cohort-based graduation rules, the backend payload assembly, the optional AI narrative flow, and the frontend chart rendering.

## Purpose

The graduation page answers five related questions:

- which visible students count as graduates in the current scope
- how effective cohorts affect on-time versus delayed graduation
- how programme, cohort, and faculty graduation rates are aggregated
- how graduation timing is shown
- which programmes and cohorts are closest to producing the first visible graduates when the snapshot is not yet graduate-complete
- whether chart-level narrative copy came from an AI provider or from the local rule-based fallback

## Main Routes

- `/graduation/`
  Graduation Analysis page shell
- `/metrics/graduation/payload/`
  Main chart, KPI, and table payload
- `/metrics/graduation/narratives/`
  Optional AI or rule-based chart narratives with diagnostics
- `/api/graduation/programmes`
  Programme filter options
- `/api/graduation/faculties`
  Faculty filter options

## Graduation Rules

The graduation page depends on the shared completion logic and then applies graduation-specific aggregation in `services/graduation_services.py`.

### Target graduation stage

`_target_period_from_programme()` resolves the documented stage with attendance type awareness:

- Masters programmes -> period `3` -> `Year 1, Semester 3`
- Engineering programmes:
  - Visiting students -> period `8` -> `Year 4, Semester 2`
  - Conventional students -> period `10` -> `Year 5, Semester 2`
- All other programmes:
  - Visiting students -> period `6` -> `Year 3, Semester 2`
  - Conventional students -> period `8` -> `Year 4, Semester 2`

### Original Cohort Isolation

**Critical Change:** All graduation rate calculations now use **strict original cohort isolation** instead of effective cohort mixing:

- **Original cohort:** Student's first registration period (true academic entry point)
- **Effective cohort:** Used only for on-time vs delayed graduation classification
- **No cohort mixing:** Students from different original cohorts are never combined in rate calculations

### Graduation qualification check

A student is counted as graduated when **BOTH** conditions are met:

1. **Progression requirement:** Student's chronological progression ≥ target period for their programme
2. **Decision requirement:** Latest visible decision indicates graduation (graduat, complet, award, pending, proceed, or resubmit dissertation)

### On-time graduation

A graduate is marked **on-time** when:
- `effective_cohort_label == original_cohort_label`

Any cohort shift makes the graduate **delayed**. This classification is used for timing analysis only.

### Individual Student Indicators

Each student record now provides meaningful indicators instead of misleading individual rates:

- `is_graduated`: Boolean graduation status
- `on_time`: Boolean on-time vs delayed classification
- `target_period`: Programme-specific graduation target
- `actual_progression`: Current chronological progression
- `steps_remaining`: Steps until graduation target
- `graduation_rate`: 100% for graduated, 0% for non-graduated (backward compatibility)

That chronological check matters because some source files store raw academic-year labels that jump or arrive out of order, for example `1.2`, `3.2`, then `3.1`. The page must not manufacture missing semesters from those labels. A master's student with only three visible registration periods is therefore one step from the documented period-4 target unless an explicit graduation-like decision exists.

## Backend Data Flow

The main service lives in `services/graduation_services.py`.

### Registration loading

The service reuses completion-side helpers to build ordered student histories and derived completion records:

- `_get_registration_history()`
- `_cohort_period_map()`
- `_build_student_records()`
- `_registration_matches_filters()`

### Student history construction

`_build_student_histories()` loads each student's ordered registrations and enriches each derived record with:

- faculty name
- period label
- academic year
- semester
- chronological progression index

Each student history also tracks the latest derived record.

### Completion lookup

`_build_completion_lookup()` aggregates completion rates by:

- `effective_cohort_label`
- chronological cohort progression period, based on ordered period IDs inside each effective cohort

This lookup powers the graduation-rate calculation for each graduate.

### Page aggregation

`get_graduation_page_data()` returns:

- `kpis`
- `charts`
- `meta`
- `students`

#### KPIs

- `total_graduated_students`
- `average_graduation_rate`
- `on_time_graduation_rate`
- `best_faculty_rate`
- `best_faculty_name`
- `graduation_rate_by_faculty`

#### Charts

- `programme_graduation_rate`
  Graduation rate by programme using original cohort isolation
- `cohort_graduation_rate`
  `(graduated / enrolled) * 100` by original cohort
- `faculty_graduation_rate`
  Weighted graduation rate by faculty using original cohort aggregation
- `graduation_timing`
  `On-time` versus `Delayed` graduate counts
- `readiness_programmes`
  Programmes with students who are one visible step from the documented graduation target
- `readiness_cohorts`
  Original cohorts with students who are one visible step from the documented graduation target

#### Meta

The payload also returns snapshot-state metadata:

- `has_graduates`
- `snapshot_message`
- `graduation_like_decision_count`
- `students_one_step_from_target`
- `students_within_two_steps`
- `readiness_population`

#### Student table

The table uses each visible graduate and shows:

- student identity
- programme
- faculty
- graduation stage
- graduation period label
- effective cohort
- original cohort
- on-time flag
- individual indicators (is_graduated, target_period, actual_progression, steps_remaining)
- graduation_rate (100% for graduates, 0% for non-graduates - backward compatibility)

## Graduation Rate Calculations

### Cohort Level Graduation Rate

```
Cohort Rate = (Number of Graduated Students in Original Cohort) ÷ (Total Students in Original Cohort) × 100
```

### Faculty Level Graduation Rate

```
Faculty Rate = (Total Graduated Students Across All Original Cohorts in Faculty) ÷ (Total Students Across All Original Cohorts in Faculty) × 100
```

### Average Graduation Rate

```
Average Rate = (Total Graduated Students Across All Original Cohorts) ÷ (Total Students Across All Original Cohorts) × 100
```

### On-Time Graduation Rate

```
On-Time Rate = (Number of Graduates with effective_cohort == original_cohort) ÷ (Total Graduated Students) × 100
```

### Key Calculation Principles

1. **Strict Original Cohort Isolation:** No mixing of students from different original entry periods
2. **Weighted Aggregation:** Faculty rates use weighted sums, not averaged percentages
3. **Academic Accuracy:** Rates represent true graduation performance, not distorted cohort mixing
4. **Backward Compatibility:** Individual graduation_rate field maintained for frontend compatibility

## Views Layer

The page controller lives in `dashboard/graduation/views.py`.

### `graduation_view()`

Renders the page shell and injects:

- the active navigation key
- the page title
- whether AI narratives are configured to be available

### `graduation_payload()`

Calls `get_graduation_page_data()` and returns the main JSON payload for the frontend.

### `graduation_narratives()`

Calls:

- `get_graduation_page_data()`
- `dashboard.graduation.ai_insights.get_graduation_card_narratives_result()`

This endpoint returns:

- `card_narratives`
- `diagnostics`

## AI Narratives

Graduation chart narratives are implemented in `dashboard/graduation/ai_insights.py`.

### Cards covered

- `programme`
- `cohort`
- `faculty`
- `timing`

### Fact-pack assembly

`build_graduation_fact_pack()` reduces the page payload into a smaller structured summary for narrative generation. It captures:

- page-level KPIs
- snapshot-state metadata
- strongest and weakest programme rows
- strongest and weakest cohort rows
- strongest and weakest faculty rows
- on-time versus delayed timing share

### Rule-based fallback

`build_rule_based_graduation_narratives()` always provides deterministic copy when:

- AI is disabled
- provider mode is `rules`
- Google or OpenAI fails
- the provider returns invalid JSON or incomplete fields

### Provider flow

`get_graduation_card_narratives_result()` attempts:

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

`dashboard/templates/dashboard/graduation.html`

Responsibilities:

- chart containers
- KPI cards
- student table shell
- story banner
- snapshot-state banner when the current data has no visible graduates yet
- readiness chart containers
- chart-note footer slots
- payload and narratives endpoint wiring through `data-*` attributes

### JavaScript

`dashboard/static/dashboard/js/graduation.js`

Responsibilities:

- fetch the graduation payload
- render KPI values
- render ECharts charts
- render readiness charts when the graduate set is empty or still building
- render the student table and CSV export
- fetch optional narratives
- show a visible diagnostics banner for loading, AI success, fallback, or endpoint failure
- show a visible snapshot-state message when the current dataset has progression records but no terminal graduation evidence
- render chart-footer badges as either `AI` or `Guidance`

### CSS

`dashboard/static/dashboard/css/graduation.css`

Responsibilities:

- graduation KPI layout
- graduation timing chart layout
- graduation table detail styling
- page-specific visual hooks not already covered by shared completion and demographic styles

## Local Development Notes

If the graduation page shows local guidance instead of AI copy during development, check these first:

1. Confirm `/metrics/graduation/narratives/` exists in `dashboard/urls.py`
2. Restart `python manage.py runserver` after adding or renaming the route
3. Hard-refresh the browser so the latest `graduation.js` bundle is loaded
4. Check the diagnostics banner on the page for timeout, missing endpoint, or fallback messages

If the graduation page shows very few or zero graduates, verify the data before changing the formula:

1. Check whether the dataset contains any explicit graduation-like decisions
2. Check whether the dataset actually reaches the terminal target periods required by the documented rules
3. Confirm the latest visible records are being evaluated relative to the student's programme start, not against raw academic-year labels alone
4. Use the readiness charts to confirm whether the snapshot is close to producing graduates but is still one or two visible steps short
5. Verify that original cohort isolation is working correctly - students should be grouped by their first registration period
6. Check that faculty rates are using weighted aggregation, not simple averaging of cohort rates
7. Confirm that individual student indicators (is_graduated, on_time, target_period) are properly calculated

### Common Issues After Refactor

1. **Low graduation rates:** This is expected! The new cohort-based system shows true academic performance
2. **Missing graduates:** Check that both progression AND decision requirements are met
3. **Faculty rate discrepancies:** Verify weighted aggregation is used instead of averaging
4. **Frontend errors:** Ensure backward compatibility graduation_rate field is present in student records

## Tests

`dashboard/graduation/tests.py` covers:

- payload shape
- no-graduates readiness metadata
- filter option endpoints
- rule-based narratives
- OpenAI narrative normalization

Recommended checks after changing graduation code:

```powershell
python manage.py test dashboard.graduation.tests
python manage.py check
```

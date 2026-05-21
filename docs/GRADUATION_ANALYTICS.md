# Graduation Analytics

This document explains the current graduation analysis implementation, including the cohort-based graduation rules, the backend payload assembly, the optional AI narrative flow, the frontend chart rendering, and the hierarchical drilldown functionality.

## Purpose

The graduation page answers seven related questions:

- which visible students count as graduates in the current scope
- how effective cohorts affect on-time versus delayed graduation
- how programme, cohort, and faculty graduation rates are aggregated
- how graduation timing is shown
- which programmes and cohorts are closest to producing the first visible graduates when the snapshot is not yet graduate-complete
- whether chart-level narrative copy came from an AI provider or from the local rule-based fallback
- how hierarchical drilldown works for faculty → departments → programmes → students

## Main Routes

- `/graduation/`
  Graduation Analysis page shell
- `/metrics/graduation/payload/`
  Main chart, KPI, and table payload
- `/metrics/graduation/narratives/`
  Optional AI or rule-based chart narratives with diagnostics
- `/metrics/graduation/drilldown/`
  Drilldown endpoint for student-level data exploration
- `/api/graduation/programmes`
  Programme filter options
- `/api/graduation/faculties`
  Faculty filter options

## Graduation Rules

The graduation page depends on the shared completion logic and then applies graduation-specific aggregation in `services/graduation_services.py`.

### Target graduation stage

`_target_period_from_programme()` resolves the documented stage based on programme type and attendance mode:

- **Masters programmes**: 3 semesters (1 year 6 months) if not delayed
- **Engineering programmes**: 
  - 10 semesters if conventional attendance
  - 8 semesters if visiting attendance
- **All other undergraduate programmes**:
  - 8 semesters if conventional attendance
  - 6 semesters if visiting attendance

The system determines attendance type by:
1. Checking student's course results for attendance type when student registration number is available
2. Fallback to programme name analysis if no student registration number is provided
3. Visiting programmes identified by keywords: "visiting", "exchange", "short"

### Effective cohort

Graduation uses the student's effective cohort after all completion-side decision shifts. This means the page inherits:

- zero-completion decisions from `services/completion_rules.py`
- effective cohort shifting from `services/completion_service.py`

### Graduate rate for one graduate

`_graduate_rate()` averages the completion rate of the graduate's effective cohort from chronological progression period `1` through the programme target period. Missing cohort periods are treated as `0%` because the documented formula averages every period from `1` to the target.

### On-time graduation

A graduate is marked on time when:

- `effective_cohort == original_cohort`
- the student's chronological progression index is less than or equal to the
  programme target period

Any cohort shift or progression beyond the documented target duration makes the
graduate delayed.

### Graduation qualification check

The page must distinguish graduation eligibility from actual graduation outcome.

A visible student becomes **graduation-eligible** when the student's
chronological registration sequence reaches or exceeds the programme target
period.

A visible student is counted as **graduated** only when both of these are true:

- the student has reached or exceeded the programme target period in the
  chronological registration sequence
- the latest visible decision explicitly indicates graduation, completion,
  award, senate approval, dissertation completion, or another recognized
  graduation outcome

That chronological check matters because some source files store raw academic-year labels that jump or arrive out of order, for example `1.2`, `3.2`, then `3.1`. The page must not manufacture missing semesters from those labels. A master's student with only three visible registration periods is therefore one step from the documented period-4 target unless an explicit graduation-like decision exists.

### Graduation decision recognition

The system recognizes graduation decisions using `_decision_indicates_graduation()` which checks for:

- "graduat", "complet", "award"
- other explicit graduation-like outcomes surfaced by institutional data, such
  as senate approval or dissertation-completion outcomes when they are present
  in the source decisions

This logic is used to separate officially recognized graduation outcomes from
mere progression to the target period.

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
  Count of all students who are officially recognized as graduated in the
  current scope
- `average_graduation_rate`
  Overall institutional graduation rate:
  `(eligible_graduated_students / eligible_students_count) * 100`
  Calculated using officially graduated students from eligible cohorts as the
  numerator and eligible students as the denominator
- `on_time_graduation_rate`
  Percentage of eligible graduates who graduated on time:
  `(eligible_on_time_graduates / eligible_graduated_students) * 100`
  On-time is defined as `effective_cohort == original_cohort` and finishing
  within the target chronological duration
- `best_faculty_rate`
  Highest graduation rate among all faculties
- `best_faculty_name`
  Name of the faculty with the highest graduation rate
- `graduation_rate_by_faculty`
  Dictionary mapping faculty names to their graduation rates

#### Charts

- `programme_graduation_rate`
  Graduation rate by programme with fields:
  - `programme_id`, `programme_name`
  - `graduation_rate` (percentage)
  - `graduated_count`, `enrolled_count`
  - `graduated_count` represents the programme's graduated-student numerator
  - `enrolled_count` represents the programme's eligible-student denominator
  - optional `official_graduated_count` can preserve a stricter explicit-award
    subset when needed for diagnostics
- `cohort_graduation_rate`
  Individual cohort graduation rates with fields:
  - `original_cohort_label` (e.g., "May 2020 - August 2020")
  - `effective_cohort_sort_index` (for chronological ordering)
  - `graduation_rate` (percentage)
  - `graduated_count`, `enrolled_count`
  - `graduated_count` represents the cohort's graduated-student numerator
  - `enrolled_count` represents the cohort's eligible-student denominator
  - optional `official_graduated_count` can preserve a stricter explicit-award
    subset when needed for diagnostics
- `faculty_graduation_rate`
  Graduation rate by faculty with hierarchical structure:
  - `faculty` (faculty name)
  - `graduation_rate` (percentage)
  - `graduated_count`, `enrolled_count`
  - `graduated_count` represents the faculty's graduated-student numerator
  - `enrolled_count` represents the faculty's eligible-student denominator
  - optional `official_graduated_count` can preserve a stricter explicit-award
    subset when needed for diagnostics
  - `hierarchy` (nested departments and programmes data)
    - `departments`: Array of department-level graduation stats
    - `programmes`: Array of programme-level graduation stats
- `graduation_timing`
  On-time versus delayed graduate counts with fields:
  - `label` ("On-time" or "Delayed")
  - `count` (number of graduates)
- `readiness_programmes`
  Programmes with students one step from graduation target
- `readiness_cohorts`
  Cohorts with students one step from graduation target

#### Meta

The payload also returns snapshot-state metadata:

- `has_graduates`
- `snapshot_message`
- `graduation_like_decision_count`
- `students_one_step_from_target`
- `students_within_two_steps`
- `readiness_population`
- `eligible_students_count`
- `graduated_students_count`
- `official_graduated_count`
- `non_eligible_students_count`
- `near_eligible_students_count`
- `delayed_students_count`
- `active_students_count`
- `at_risk_students_count`
- `faculty_eligible_students`
- `programme_eligible_students`

#### Student table

The table uses each visible graduate and shows:

- student identity
- programme
- faculty
- current displayed academic level
- current displayed academic level label
- effective cohort
- original cohort
- on-time flag
- graduation rate

The payload also preserves the programme target stage separately for consumers
that need it:

- `target_graduation_stage`
- `target_graduation_period_label`

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

### `graduation_drilldown()`

Calls `build_graduation_drilldown_data()` in `dashboard/graduation/services.py` to provide student-level drilldown data.

Supports chart keys:
- `programme_load` - Students in specific programme
- `cohorts` - Students in specific cohort
- `faculties` - Students in specific faculty
- `departments` - Students in specific department
- `programmes` - Students in specific programme

Returns paginated student data with:
- `rows` - Student details (name, registration number, programme, etc.)
- `total_count` - Total matching students
- `page` - Current page number
- `page_size` - Items per page
- `page_count` - Total pages

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
- render KPI values with safe data access (`data?.kpis?.key || default`)
- render ECharts charts with proper backend key mapping
- render readiness charts when the graduate set is empty or still building
- render the student table and CSV export
- fetch optional narratives
- show a visible diagnostics banner for loading, AI success, fallback, or endpoint failure
- show a visible snapshot-state message when the current dataset has progression records but no terminal graduation evidence
- render chart-footer badges as either `AI` or `Guidance`
- implement hierarchical drilldown for faculty charts (Faculty → Departments → Programmes → Students)
- handle chart click events with proper data mapping
- manage pagination with filter preservation
- display professional hierarchical drilldown modal with interactive department/programme cards

#### Chart Data Mapping

The frontend correctly maps backend response keys:

- `data.charts.programme_graduation_rate` → Programme chart
- `data.charts.cohort_graduation_rate` → Cohort chart (uses `original_cohort_label`)
- `data.charts.faculty_graduation_rate` → Faculty chart (uses `faculty` field)
- `data.charts.graduation_timing` → Timing chart (uses `label` and `count`)
- `data.charts.readiness_programmes` → Readiness programme chart
- `data.charts.readiness_cohorts` → Readiness cohort chart

#### Hierarchical Drilldown

The faculty chart supports hierarchical drilldown:

1. **Faculty Level**: Shows overall faculty graduation rate
2. **Department Level**: Click on faculty to see departments with graduation rates
3. **Programme Level**: Click on department to see programmes with graduation rates
4. **Student Level**: Click on any level to see individual student details

The hierarchical modal displays:
- Department cards with graduation statistics
- Programme cards with graduation statistics
- Interactive navigation between levels
- "View All Students" option for faculty-level drilldown

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

If charts are not displaying correctly:

1. Check browser console for JavaScript errors
2. Verify backend response structure matches expected keys
3. Ensure data access uses safe navigation (`data?.charts?.key || []`)
4. Check that chart data mapping uses correct field names (e.g., `original_cohort_label` vs `effective_cohort_label`)
5. Verify label overflow fixes are applied (45-degree rotation, truncation)

If drilldown is not working:

1. Verify `/metrics/graduation/drilldown/` endpoint exists and is functional
2. Check that chart click handlers are properly attached
3. Ensure drilldown modal CSS is loaded
4. Verify that `window.graduationAnalysis` is globally accessible for hierarchical drilldown
5. Check that pagination preserves filter parameters correctly

## Tests

`dashboard/graduation/tests.py` covers:

- payload shape
- no-graduates readiness metadata
- filter option endpoints
- rule-based narratives
- OpenAI narrative normalization

## Key Calculation Methods

### Average Graduation Rate

Formula: `(eligible_graduated_students / eligible_students_count) * 100`

- `eligible_graduated_students`: Students who are academically eligible and are
  also officially recognized as graduated
- `eligible_students_count`: Visible students whose chronological progression
  has reached or exceeded the programme target period
- Newly admitted or not-yet-mature cohorts do not dilute this rate
- This KPI measures graduation conversion among students who have reached
  graduation maturity, not eligibility penetration through the whole dataset

### Faculty Graduation Rate

Formula: `(total_faculty_graduated / total_faculty_eligible_students) * 100`

- `total_faculty_graduated`: Officially graduated students across all faculty cohorts
- `total_faculty_eligible_students`: Eligible students across all faculty cohorts
- Weighted aggregation (not simple average of programme rates)
- Larger cohorts have proportionally more impact on rate
- Best faculty rate is the maximum value from `graduation_rate_by_faculty`

### Individual Cohort Graduation Rate

Formula: `(cohort_graduated_students / cohort_eligible_students) * 100`

- Calculated for each individual cohort separately
- Uses `original_cohort_label` for cohort identification
- Sorted by `effective_cohort_sort_index` for chronological display
- `graduated_count` in the chart row is the graduated-student numerator
- `enrolled_count` in the chart row is the eligible-student denominator
- Enables cohort-by-cohort graduation-conversion analysis among mature cohorts

### Programme Graduation Rate

Formula: `(programme_graduated_students / programme_eligible_students) * 100`

- `graduated_count` in the chart row is the graduated-student numerator
- `enrolled_count` in the chart row is the eligible-student denominator
- Optional `official_graduated_count` preserves the students who also have an
  explicit graduation-like decision when that distinction is exposed

### On-Time Graduation Rate

Formula: `(eligible_on_time_graduates / eligible_graduated_students) * 100`

- `eligible_on_time_graduates`: Graduated students where
  `effective_cohort == original_cohort` and `chronological_progression_index <= target_period`
- `eligible_graduated_students`: Graduated students from eligible cohorts
- Measures timeliness among officially graduated students who already satisfy
  the academic eligibility requirements
- Any cohort shift makes a graduate "delayed"

### Displayed Level Versus Target Stage

The graduation page now separates two concepts that were previously conflated:

- `graduation_stage` and `graduation_period_label`
  These now represent the student's current displayed academic level, aligned
  with the student detail page and built from `dashboard.student_history`.
- `target_graduation_stage` and `target_graduation_period_label`
  These represent the programme's documented target graduation stage.

This prevents a student list row from showing a target such as `Year 5, Semester 2`
when the detail page is intentionally displaying the student's current rebased
visible level.

Recommended checks after changing graduation code:

```powershell
python manage.py test dashboard.graduation.tests
python manage.py check
```

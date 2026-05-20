# Student History Helpers

This document explains [`dashboard/student_history.py`](../dashboard/student_history.py), which is the shared backend helper module responsible for building a student's academic timeline, repeated-attempt history, and transcript summaries.

## Purpose

`student_history.py` exists to keep student academic history logic in one place instead of scattering it across views.

It is used to:

- resolve a registration's academic year and semester
- sort registrations into a stable academic order
- group registrations into displayed student semesters
- preserve repeat, carry, and supplementary attempt history
- support cumulative grade calculations
- support transcript summary totals
- control how semester period labels are shown in the student dropdowns
- control when repeated-semester section headers appear in the module table

The file is especially important for students with:

- repeated semesters
- carried courses
- supplementary attempts
- imported data where raw academic stages are duplicated or non-contiguous

## Main Responsibilities

### 1. Parse academic structure

The module first converts raw registration data into a normalized academic structure.

Key helper:

- `extract_registration_year_semester(registration)`

Behavior:

- reads `registration.period.academic_year`
- reads `registration.period.semester`
- falls back to parsing numbers from the period name if needed
- guarantees a minimum value of `1` for both year and semester

This is the base structural signal used by the rest of the file.

### 2. Sort registrations consistently

Key helper:

- `sort_registrations_by_structure(registrations)`

Sorting order:

1. parsed academic year
2. parsed semester
3. period external id
4. registration id

This keeps the timeline stable even when the raw import order is noisy.

### 3. Build displayed semester groups

Key helper:

- `build_student_timeline(registrations)`

This is the central function in the file.

It converts a flat list of registrations into grouped semester containers. Each group includes:

- a display key such as `1:1`
- display year and semester labels
- raw imported year and semester values
- all registrations merged into that displayed semester
- all result rows belonging to that displayed semester
- the latest registration in the group
- a combined period display string

Two display outputs now depend on the same grouped structure:

- `period_display`
  Used by the year/semester dropdown on the student detail page
- `result_sections`
  Used by the modules table when repeated-level history needs to be split by period

The returned structure looks like:

```python
{
    "groups": [...],
    "groups_by_key": {...},
}
```

## Repeat And Merge Logic

The hardest part of this file is deciding when multiple registrations should stay in the same displayed semester.

### Why this exists

Some imported students have multiple registrations with the same raw academic year and semester, for example:

- `September 2021 - December 2021` -> `1,1`
- `May 2022 - August 2022` -> `1,1`
- `September 2022 - December 2022` -> `1,1`

Not all of those should be treated the same way.

- A true repeat should remain in the same displayed semester bucket.
- A later registration with a mostly new module set should become the next displayed semester, even if the imported raw stage is still the same.

### Course-overlap rule

Key helpers:

- `_registration_course_codes(registration)`
- `_should_merge_with_group(group, year, semester, registration_course_codes)`

Current merge behavior:

- registrations can only merge if the raw year and raw semester match the current group
- if the registration has no course rows, it can still merge into the current group
- if the registration has courses, at least 50% of its course codes must overlap with the group's existing course set

This rule is meant to separate:

- true repeat attempts of the same semester
- new module sets that were imported with the same raw stage label

## Period Label Display Rules

Student detail now uses two different period-label behaviors depending on whether
the selected displayed semester is an ordinary sitting or a repeated-history
semester.

### Dropdown period label

`group["period_display"]` is built with these rules:

- if the group contains repeat-history attempts, show the merged audit history
  such as `May 2022 - August 2022 / September 2022 - December 2022`
- otherwise show only the latest single period name for that displayed semester

This avoids confusing users with joined period strings for normal semesters.

### Results-table section headers

The student detail modules table only shows centered period-section header rows
when the selected displayed semester actually contains repeated or carried
history split across more than one registration period.

For ordinary students:

- `result_sections` may still exist internally
- but the template should render a flat table without centered section-title rows

For repeated-level students:

- the latest repeat period should be shown first
- earlier attempts should be shown below it

## Display-Year Rebasing

Imported academic stages are not always clean or contiguous. Some students have raw sequences such as:

- `2,1`
- `2,2`
- `3,1`
- `5,1`

To keep the student detail UI readable, `build_student_timeline()` rebases the final displayed groups into contiguous progression slots:

- first displayed group -> `Year 1 Semester 1`
- second displayed group -> `Year 1 Semester 2`
- third displayed group -> `Year 2 Semester 1`
- fourth displayed group -> `Year 2 Semester 2`

This rebasing only affects presentation.

The raw imported structure is still preserved on each group and row as:

- `raw_year`
- `raw_semester`

## Attempt History

Each course result row tracks attempt history across the full ordered registration list.

Fields added to each attempt row include:

- `attempt_number`
- `is_repeat_attempt`
- `is_carried_attempt`
- `is_supplementary_attempt`
- `attempt_tags`
- `original_year`
- `original_semester`

Tag examples:

- `First Attempt`
- `Attempt 2`
- `Repeated`
- `Carried`
- `Supplementary`

This allows the student detail page and transcript page to show both the latest state and the audit trail.

## Cumulative Average

Key helper:

- `calculate_cumulative_average(groups, selected_group_key=None)`

Behavior:

- walks groups in order
- keeps only the latest visible attempt per course code
- averages only rows with actual marks
- optionally stops at a selected group for cumulative-as-of-this-semester calculations

This prevents repeated attempts from being double-counted.

On the student detail page, the displayed cumulative grade is now rounded to a
whole number for presentation, even though the helper still returns a numeric
average value suitable for further calculation.

## Transcript Summary

Key helper:

- `build_transcript_summary(groups)`

Behavior:

- uses the latest attempt per course
- computes:
  - total courses
  - total passed
  - total failed
  - average mark
  - pass rate
  - completion rate

This summary is used by the transcript view.

## Where It Is Used

`student_history.py` feeds multiple student-facing flows.

Primary consumers:

- `dashboard.views.student_detail`
- `dashboard.views.student_transcript`
- academic-level and demographic helpers that need consistent year/semester resolution

Because this file is shared, changes here can affect:

- student detail dropdown tabs
- repeated-semester table grouping
- transcript attempt ordering
- cumulative grade values
- year and semester labels across analytics helpers

## Safe Change Guidelines

When editing this file:

1. Preserve the distinction between raw imported stages and displayed stages.
2. Be careful with merge logic for repeated semesters.
3. Re-check cumulative average behavior after changing grouping.
4. Re-check transcript rows after changing attempt ordering.
5. Run the student-detail and transcript tests, especially repeat-related cases.

## Recommended Tests To Watch

Relevant tests live in [`dashboard/tests.py`](../dashboard/tests.py).

Pay special attention to tests covering:

- repeated semesters collapsing into one tab
- repeated semester results split by period
- ordinary semesters hiding centered section headers
- non-contiguous imported years rebased for display
- new module sets promoted out of repeated-semester buckets
- non-repeat dropdown period labels showing only one period
- transcript retake history

## Known Design Tradeoff

The grouping logic intentionally mixes two goals:

- fidelity to imported raw registration history
- a clean and understandable student-facing progression view

That means the module does not simply trust imported `academic_year` and `semester` values as final truth for UI display. Instead, it interprets them using course overlap and registration order to produce a more accurate displayed progression.

This tradeoff is deliberate and supports messy real-world registrar imports.

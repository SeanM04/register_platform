# Risk Backend

This package owns the risk dashboard feature backend.

## Structure

- `views.py`
  HTTP entrypoints for the risk page and metrics endpoint
- `services.py`
  Data shaping, scoring, and aggregation logic for the risk dashboard
- `presenters.py`
  Template-context assembly for the risk page
- `ai_insights.py`
  Rule-based and AI-assisted overview narratives for the chart cards
- `constants.py`
  Feature-local constants such as risk bands, summary cards, and driver labels
- `tests.py`
  Feature-specific tests for risk scoring, page context, and AI narrative behavior

## Shared Dependencies

For now, shared dashboard helpers still live outside this package:

- filter and layout helpers in `dashboard/views.py`
- shared academic models in `dashboard/models.py`
- the institutional `insights` page in `dashboard/views.py`, which calls thin wrapper
  functions that delegate into this package

That is intentional. This creates a clean feature boundary first without forcing a larger
dashboard-wide reorganization in the same change.

## How Risk Levels Are Categorised

The risk page uses a simple additive score in `services.py` to classify each student.

### Scoring Inputs

- `Average mark`
  - below `50%` adds `+3`
  - from `50%` to `59%` adds `+1`
- `Failed modules`
  - `3+` failed modules adds `+3`
  - `2` failed modules adds `+2`
  - `1` failed module adds `+1`
- `Carried modules`
  - `2+` carried modules adds `+2`
  - `1` carried module adds `+1`
- `Adverse academic decision`
  - decisions such as `retake`, `repeat`, `fail`, `excluded`, `withdrawn`, `dropped`, or `suspended` add `+2`

### Final Risk Level

After those inputs are combined:

- `High Risk`: score `4+`
- `Medium Risk`: score `2-3`
- `Low Risk`: score `0-1`

### Chart Bands

The story page uses two related concepts:

- `Risk level`
  - the action register and Chapter 2 level/programme charts work with `High Risk` and `Medium Risk`
  - `Low Risk` students are excluded from the action register
- `Risk band`
  - the Chapter 1 distribution chart uses broader score bands across the full visible cohort:
  - `Critical`: `6+`
  - `High`: `4-5`
  - `Moderate`: `2-3`
  - `Low`: `0-1`
  - the bracketed values are risk bands, not failed-module counts

### Driver Summary

- The `3+ Failed Modules` summary card counts students with three or more failed modules.
- The risk distribution note shown under the chart should read: `Values in brackets represent risk bands.`

This distinction is intentional. The page still keeps the full cohort visible in the overview,
but the detailed intervention views focus on students who already need support attention.

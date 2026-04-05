# Academic Levels Backend

This package owns the academic-level dashboard feature backend.

## Structure

- `views.py`
  HTTP entrypoints for the academic-level page and metrics endpoint
- `services.py`
  Data shaping and aggregation logic for academic-level analytics
- `presenters.py`
  Template-context assembly for the academic-level page
- `ai_insights.py`
  Rule-based and AI-assisted narrative generation for the three overview cards
- `constants.py`
  Feature-local constants such as the pass target and summary card spec
- `tests.py`
  Feature-specific tests for academic-level analytics and AI narrative behavior

## Shared Dependencies

For now, shared dashboard helpers still live outside this package:

- filter and layout helpers in `dashboard/views.py`
- shared academic models in `dashboard/models.py`

That is intentional. This refactor creates a clean feature boundary first without forcing a
larger dashboard-wide reorganization in the same change.

# Demographics Backend

This package owns the demographics dashboard feature backend.

## Structure

- `views.py`
  HTTP entrypoints for the demographics page and metrics endpoint
- `services.py`
  Data shaping and aggregation logic for demographics analytics
- `presenters.py`
  Template-context assembly for the demographics page
- `constants.py`
  Feature-local constants such as the page title and summary card spec
- `tests.py`
  Feature-specific tests for demographics behavior

## Shared Dependencies

For now, shared dashboard helpers still live outside this package:

- filter and layout helpers in `dashboard/views.py`
- shared academic models in `dashboard/models.py`

That is intentional. This creates a clean feature boundary first without forcing a larger
dashboard-wide reorganization in the same change.

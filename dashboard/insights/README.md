# Insights Backend

This package owns the institutional `Insights` dashboard backend.

## Structure

- `views.py`
  HTTP entrypoint for the insights page
- `services.py`
  Story data shaping for risk pressure, faculty concentration, drivers, recommendations, and action queues
- `presenters.py`
  Template-context assembly for the insights page
- `ai_insights.py`
  Rule-based and AI-assisted overview narratives for the story cards
- `constants.py`
  Feature-local constants such as page metadata and narrative card keys
- `tests.py`
  Feature-specific tests for story payloads and AI narrative behavior

## Story Model

The insights page is the executive cross-feature surface for the dashboard.

It does not replace the specialist pages:

- `risk/` stays the operational intervention register
- `academic-level/` stays the level progression lens
- `demographic/` stays the cohort composition lens

Instead, `insights/` pulls the strongest live institutional signals into one page so an operator can answer:

1. How much risk pressure is visible right now?
2. Where is capacity concentrating?
3. What is driving intervention demand?
4. Which students and actions need attention next?

## Shared Dependencies

For now, some shared helpers still live outside this package:

- filter and layout helpers in `dashboard/views.py`
- risk-profile scoring and flagged-student formatting in `dashboard/risk/services.py`
- shared academic models in `dashboard/models.py`

That is intentional. This keeps the insights page maintainable without forcing a broader shared-services refactor in the same change.

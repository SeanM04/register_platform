# AI Insights

This document explains the AI-assisted narrative flow used on the academic-level,
demographics, risk, overview, and institutional insights dashboards.

Important:

- the academic-level AI narrative logic now lives in
  `dashboard/academic_levels/ai_insights.py`, and it powers the three overview cards on
  `dashboard/academic_level.html`
- the demographics AI narrative logic now lives in `dashboard/demographics/ai_insights.py`,
  and it powers the five overview cards on `dashboard/demographic.html`
- the risk AI narrative logic now lives in `dashboard/risk/ai_insights.py`, and it powers
  the four overview cards on `dashboard/risk.html`
- the landing-page overview AI narrative logic now lives in `dashboard/overview/ai_insights.py`,
  and it powers the four chart cards on `dashboard/home.html`
- the institutional insights AI narrative logic now lives in `dashboard/insights/ai_insights.py`,
  and it powers the four overview cards on `dashboard/insights.html`

## 1. Files Involved

- `dashboard/academic_levels/views.py`
  Handles the academic-level page and metrics endpoints
- `dashboard/academic_levels/services.py`
  Builds the filtered academic-level aggregates
- `dashboard/academic_levels/presenters.py`
  Shapes the template context for the academic-level page
- `dashboard/academic_levels/ai_insights.py`
  Converts those aggregates into rule-based or AI-assisted card narratives
- `dashboard/templates/dashboard/academic_level.html`
  Serializes the narrative payload with `json_script`
- `dashboard/static/dashboard/js/academic_level.js`
  Reads the payload and injects the insight and action copy into the three chart cards
- `dashboard/academic_levels/tests.py`
  Covers the default rule-based path plus the OpenAI and Google provider paths

## 2. What The Feature Produces

The backend returns one payload with three cards:

- `gender`
- `top_enrolment`
- `pass_trend`

Each card uses this shape:

```json
{
  "source": "rules",
  "cards": {
    "gender": {
      "insight": "Short sentence for the card heading area.",
      "action": "Short sentence for the card footer area.",
      "severity": "stable",
      "confidence": "medium"
    }
  }
}
```

Allowed severities are `stable`, `medium`, and `high`.

Allowed confidence values are `low`, `medium`, and `high`.

## 3. End-To-End Flow

1. `academic_level_view()` in `dashboard/academic_levels/views.py` calls `build_academic_level_data()`.
2. `build_academic_level_data()` in `dashboard/academic_levels/services.py` shapes the filtered registrations into:
   `level_rows`, `level_chart_rows`, `gender_performance_rows`, and
   `programme_performance_rows`.
3. `get_academic_level_card_narratives()` in `dashboard/academic_levels/ai_insights.py` receives that
   dictionary.
4. The module always builds a deterministic fallback first with
   `build_rule_based_academic_level_narratives()`.
5. If settings allow AI, the module turns the dashboard aggregates into a compact fact pack,
   prompts the selected provider, and validates the JSON response.
6. The template writes the final narrative payload into
   `academic-level-card-narratives` via Django `json_script`.
7. `dashboard/static/dashboard/js/academic_level.js` reads that JSON and updates the
   visible chart-card copy and AI badge state.

## 4. Input Data The Module Depends On

`dashboard/academic_levels/ai_insights.py` only uses three parts of `academic_level_data`:

- `level_chart_rows`
  Per-level pass rate, average mark, registrations, and programme breakdowns
- `gender_performance_rows`
  Cohort split, pass rate, and marks by gender bucket
- `programme_performance_rows`
  Programme enrolment totals, pass rates, and level breakdowns

The module does not query the database itself. It assumes the view already applied all
current filters and search terms.

## 5. Rule-Based Fallback Logic

The fallback path exists so the page still works when:

- AI is disabled
- API keys are missing
- a provider times out
- the provider returns invalid JSON
- the provider omits required fields

The fallback also provides baseline `severity` and `confidence` values. When AI output is
accepted, those baseline values are still used as guard rails.

## 6. Provider Selection

The main settings live in `registrar_platform/settings.py`.

- `AI_INSIGHTS_PROVIDER`
  Accepts `rules`, `auto`, `google`, or `openai`
- `AI_INSIGHTS_ENABLED`
  Global gate for AI insights
- `GOOGLE_API_KEY`
  Required for Gemini requests
- `GOOGLE_INSIGHTS_MODEL`
  Defaults to `gemini-2.5-flash-lite`
- `GOOGLE_INSIGHTS_TIMEOUT_SECONDS`
  Timeout for Gemini requests
- `OPENAI_API_KEY`
  Required for OpenAI requests
- `OPENAI_INSIGHTS_ENABLED`
  Additional OpenAI gate, especially relevant in `auto` mode
- `OPENAI_INSIGHTS_MODEL`
  Defaults to `gpt-5.4-mini`
- `OPENAI_INSIGHTS_TIMEOUT_SECONDS`
  Timeout for OpenAI requests

Actual selection order:

- `rules`
  Always return the deterministic fallback
- `google`
  Try Gemini only; on failure return the fallback
- `openai`
  Try OpenAI only; on failure return the fallback
- `auto`
  Try Gemini first when `GOOGLE_API_KEY` is present, then try OpenAI only when
  `OPENAI_INSIGHTS_ENABLED` and `OPENAI_API_KEY` are both set, otherwise return the fallback

## 7. Safety Rails

The AI path is intentionally constrained:

- the prompt tells the model to use only supplied facts
- both providers are asked for strict JSON matching the expected schema
- missing or invalid `severity` and `confidence` values are normalized
- AI is not allowed to downgrade severity below the rule-based baseline
- requests are wrapped in `try/except`, so failures stay invisible to the user and only log warnings

## 8. Frontend Behavior

The frontend uses the AI or rule-based narrative only for the overview state of the three
chart cards.

When a user drills into:

- a specific programme in the top-enrolment card, or
- a specific academic level in the pass-trend card

the detailed narrative text is generated locally in `academic_level.js` from the already
available chart data. No extra AI request is made in the browser.

## 9. Caching

Both provider request helpers use `@lru_cache(maxsize=64)`.

That means:

- identical fact packs reuse the same provider response inside the same Django process
- the cache is per-process, not shared across deployments
- changing provider settings does not invalidate already cached fact-pack responses until the
  process restarts or the cache is cleared

## 10. If You Need To Extend This

If you add or rename a card, update all of these together:

- `ACADEMIC_LEVEL_NARRATIVE_SCHEMA` in `dashboard/academic_levels/ai_insights.py`
- `build_academic_level_fact_pack()`
- `build_rule_based_academic_level_narratives()`
- `_normalize_ai_narrative_payload()`
- the `academic_level.html` card placeholders and element IDs
- the matching narrative readers in `academic_level.js`
- the tests in `dashboard/tests.py`

## 11. Demographics Dashboard

The demographics page now follows the same safe pattern as academic levels, but with a
different card set:

- `gender`
- `location`
- `location_mix`
- `programme`
- `origin_map`

Files involved:

- `dashboard/demographics/views.py`
  Handles the demographics page and metrics endpoint
- `dashboard/demographics/services.py`
  Builds the filtered demographic aggregates
- `dashboard/demographics/presenters.py`
  Shapes the template context and attaches the final narrative payload
- `dashboard/demographics/ai_insights.py`
  Converts demographic aggregates into rule-based or AI-assisted overview narratives
- `dashboard/templates/dashboard/demographic.html`
  Serializes the narrative payload with `json_script`
- `dashboard/static/dashboard/js/demographic/narratives.js`
  Reads the payload, applies AI badges when relevant, and falls back to local rules when
  the backend payload is missing
- `dashboard/demographics/tests.py`
  Covers the default rule path plus OpenAI and Google provider paths

Important difference from academic levels:

- the demographics story banner still stays rule-based in the browser
- AI is only used for the overview card copy and action text
- drilldown states such as location click-through and map marker popups stay local and
  deterministic

## 12. Risk Dashboard

The risk page now follows the same safe pattern, with these overview cards:

- `distribution`
- `drivers`
- `levels`
- `programmes`

Files involved:

- `dashboard/risk/views.py`
  Handles the risk page and metrics endpoint
- `dashboard/risk/services.py`
  Builds the filtered risk aggregates, chart rows, and action-register data
- `dashboard/risk/presenters.py`
  Shapes the template context and attaches the final narrative payload
- `dashboard/risk/ai_insights.py`
  Converts risk aggregates into rule-based or AI-assisted overview narratives
- `dashboard/templates/dashboard/risk.html`
  Serializes the narrative payload with `json_script`
- `dashboard/static/dashboard/js/risk/narratives.js`
  Reads the payload, applies AI badges when relevant, and keeps the story banner rule-based
- `dashboard/risk/tests.py`
  Covers the default rule path plus OpenAI and Google provider paths

Important note for the risk page:

- the risk page uses AI only for chart-card overview copy
- the operational register, student rows, and page-wide story banner remain deterministic
- no browser-side AI request is made during chart interaction or search

## 13. Institutional Insights Dashboard

The institutional insights page now follows the same safe pattern, with these overview cards:

- `distribution`
- `faculty_load`
- `faculty_pressure`
- `drivers`

Files involved:

- `dashboard/insights/views.py`
  Handles the insights page entrypoint
- `dashboard/insights/services.py`
  Builds the filtered institutional story payload, action cards, and flagged queue
- `dashboard/insights/presenters.py`
  Shapes the template context and attaches the final narrative payload
- `dashboard/insights/ai_insights.py`
  Converts insights aggregates into rule-based or AI-assisted overview narratives
- `dashboard/templates/dashboard/insights.html`
  Serializes the narrative payload with `json_script`
- `dashboard/static/dashboard/js/insights/narratives.js`
  Reads the payload, applies AI badges when relevant, and keeps the story banner rule-based
- `dashboard/insights/tests.py`
  Covers the default rule path plus OpenAI and Google provider paths

Important difference from the specialist pages:

- the institutional insights page is the executive cross-feature surface
- AI is only used for chart-card overview copy and footer actions
- recommendations, flagged students, and the page-wide story banner remain deterministic

## 14. Landing Overview Dashboard

The landing page now follows the same safe pattern, with these overview cards:

- `outcomes`
- `risk`
- `faculty`
- `progress`

Files involved:

- `dashboard/overview/views.py`
  Handles the landing dashboard entrypoint and metric hydration endpoint
- `dashboard/overview/services.py`
  Builds the filtered overview story payload, chart rows, and route cards
- `dashboard/overview/presenters.py`
  Shapes the template context and attaches the final narrative payload
- `dashboard/overview/ai_insights.py`
  Converts overview aggregates into rule-based or AI-assisted chart-card narratives
- `dashboard/templates/dashboard/home.html`
  Serializes the narrative payload with `json_script`
- `dashboard/static/dashboard/js/home/narratives.js`
  Reads the payload, applies AI badges when relevant, and keeps the story banner deterministic
- `dashboard/overview/tests.py`
  Covers the default rule path plus OpenAI and Google provider paths

Important note for the landing page:

- AI is only used for the four chart-card overview narratives
- the top hero banner and “Where To Explore Next” route cards remain deterministic
- no browser-side AI request is made during chart interaction

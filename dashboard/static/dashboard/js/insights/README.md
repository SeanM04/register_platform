# Insights Frontend

This folder owns the page-scoped runtime for the institutional insights dashboard.

## Structure

- `index.js`
  Page bootstrap and chart lifecycle wiring
- `context.js`
  Reads the server-rendered JSON payloads and caches important DOM nodes
- `shared.js`
  Shared ECharts helpers, tooltip builders, JSON parsing, and empty-state handling
- `narratives.js`
  Story banner rendering plus overview copy for each chart card
- `distribution.js`
  Institutional risk-distribution chart controller
- `faculty_load.js`
  Registration-load-by-faculty chart controller
- `faculty_pressure.js`
  Flagged-student pressure-by-faculty chart controller
- `drivers.js`
  Shared intervention-trigger ranking chart controller
- `fullscreen.js`
  Full-screen behavior for insights chart cards

## Maintenance Notes

- Keep the story banner and chart narratives aligned with the payload shape from
  `dashboard/insights/presenters.py`.
- Add or rename chart sections in both the template and `context.js`.
- Prefer keeping each new chart in its own controller module instead of growing `index.js`.

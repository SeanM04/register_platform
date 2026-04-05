# Risk Frontend

This folder owns the page-scoped runtime for the risk dashboard.

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
  Risk-band distribution chart controller
- `drivers.js`
  Shared risk-driver ranking chart controller
- `levels.js`
  Academic-level concentration chart controller
- `programmes.js`
  Programme concentration chart controller
- `fullscreen.js`
  Full-screen behavior for risk chart cards
- `search.js`
  Debounced action-register search behavior

## Maintenance Notes

- Keep the story banner and card narratives aligned with the payload shape from
  `dashboard/risk/presenters.py`.
- Add or rename chart sections in both the template and `context.js`.
- Prefer keeping each new chart in its own controller module instead of growing `index.js`.

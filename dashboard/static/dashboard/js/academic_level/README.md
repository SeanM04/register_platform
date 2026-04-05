# Academic Level Frontend Modules

This page is split by responsibility, not only by graph.

## Structure

- `index.js`
  Page bootstrap that wires the modules together
- `context.js`
  Reads server-rendered JSON payloads and resolves DOM references
- `shared.js`
  Cross-cutting helpers for formatting, tooltips, chart setup, and ECharts utilities
- `narratives.js`
  Story-banner logic, AI badge formatting, hint text, and card narrative builders
- `gender.js`
  Gender chart rendering and its narrative wiring
- `pass_trend.js`
  Pass-trend chart rendering, drilldown state, and table jump behavior
- `top_programme.js`
  Top-programme chart rendering and drilldown state
- `search.js`
  Search debounce behavior
- `fullscreen.js`
  Full-screen controls for the chart cards

## Why This Split

For maintenance and scale, the safest boundary is:

1. shared page infrastructure
2. shared narrative/presentation rules
3. one controller per interactive section

That means a future change to one graph usually stays inside one module, while changes to
tooltips, AI badge rules, or data parsing stay centralized instead of being duplicated across
three chart files.

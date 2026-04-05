# Demographics Frontend Modules

This page is split by responsibility so chart work stays localized.

## Structure

- `index.js`
  Page bootstrap that wires the demographics modules together
- `context.js`
  Reads server-rendered JSON payloads and resolves DOM references
- `shared.js`
  Cross-cutting ECharts and formatting helpers
- `narratives.js`
  Story-banner logic, AI overview narrative readers, badge formatting, and chart-card copy builders
- `gender.js`
  Gender distribution chart controller
- `locations.js`
  Birth-location concentration chart controller
- `location_mix.js`
  Birth-location and gender heatmap controller
- `origin_map.js`
  MapLibre-powered geographic student-origin map controller
- `programme_mix.js`
  Programme gender composition chart controller
- `fullscreen.js`
  Full-screen controls for the chart cards

## Why This Split

It mirrors the maintainability pattern used on the academic-level page:

1. shared page infrastructure
2. shared narrative and chart helpers
3. one controller per interactive section

That keeps future graph changes isolated while still centralizing the reusable page behavior.

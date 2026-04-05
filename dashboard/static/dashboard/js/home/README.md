## Home Dashboard JS

This folder owns the landing-page runtime.

### Structure

- `index.js`: page bootstrap and resize/fullscreen orchestration
- `context.js`: reads server JSON payloads and DOM hooks
- `shared.js`: parsing, tooltips, colors, and chart helpers
- `narratives.js`: renders the landing-page story banner and applies rule-based or AI-backed chart-card narratives
- `outcomes.js`: assessment outcome donut
- `risk_distribution.js`: cohort risk-band chart
- `faculty_load.js`: registration load by faculty
- `progress.js`: registration decision status chart
- `fullscreen.js`: full-screen chart card controls

### Maintainer note

Keep the landing page focused on orientation:

- show the current institutional state quickly
- make the charts easy to scan
- route users into specialist pages instead of rebuilding every page inside the home dashboard
- keep the hero banner deterministic while allowing the chart cards to use backend AI narratives when enabled

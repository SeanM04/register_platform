## Programme Frontend Modules

This folder keeps the story-first Programmes page maintainable by splitting page behavior
into small page-owned modules instead of growing a single `programme.js` file.

### Module map

- `index.js`: page bootstrap, resize handling, and fullscreen wiring
- `context.js`: reads the server-rendered JSON payloads and DOM references
- `shared.js`: chart helpers, tooltip builders, formatting, and fallback utilities
- `narratives.js`: deterministic banner copy plus AI/rule-based chart-card text handling
- `load.js`: visible registrations by programme chart
- `departments.js`: department concentration chart
- `quality.js`: weakest pass-rate programmes chart
- `performance.js`: registrations-versus-pass-rate scatter view
- `register.js`: debounced search behavior for the lower reference register
- `fullscreen.js`: full-screen chart card handling

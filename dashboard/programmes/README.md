## Programmes Dashboard

This feature package owns the upgraded story-first programmes page.

### What it does

- shapes the summary cards for visible programmes, registrations, students, and weighted pass rate
- builds the chart rows for programme load, department concentration, weakest pass rates, and the registrations-versus-quality map
- keeps the searchable programme register available as the detailed reference view

### Why it exists

The old Programmes tab was table-first and lived directly inside `dashboard/views.py`.
This package keeps the page maintainable by separating:

- `services.py`: programme aggregation, ranked chart rows, and scope pills
- `ai_insights.py`: safe rule-based and optional AI-assisted chart-card narratives
- `presenters.py`: lightweight shell-context assembly for first paint
- `views.py`: HTTP entrypoints for the shell page, metric hydration, chart payload hydration, and optional narrative hydration

### Progressive loading architecture

The page now loads in three passes instead of blocking the first HTML response on every chart payload:

1. the HTML shell renders immediately with the layout, summary-card placeholders, scope pills, and empty chart/register containers
2. the browser requests `programme-payload` in the background and hydrates the story banner, charts, and register rows
3. when AI narratives are enabled, the browser requests `programme-narratives` separately so slower provider calls do not hold back the operational data

This keeps tab switches noticeably shorter because the browser can paint the new workspace before the heavier aggregation and optional AI work finishes.

### Important modelling choice

The page now uses a **weighted pass rate** for the headline summary card.

That means the pass-rate card is based on:

- total passing marked results across the visible programmes
- divided by total marked results across the visible programmes

This is more trustworthy than a simple average of programme pass rates, because it prevents
a very small programme from influencing the headline as much as a very large programme.

### Storytelling intent

This page should answer three questions quickly:

1. Which programmes currently carry the most visible load?
2. Which programmes or departments need academic review first?
3. Which detailed programme rows should the user inspect in the register next?

### Next performance steps

- add short-lived caching for `programme-payload` and `programme-narratives` by filter scope
- precompute the largest dashboard aggregates for the most common faculty and period combinations
- lazy-load the register rows only when the user reaches the register section
- keep AI hydration optional and asynchronous so the page remains usable even when providers are slow

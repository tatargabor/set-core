# Spec: UI Completeness Rules

## Status: new

## Requirements

### REQ-UI-NO-PLACEHOLDERS: No placeholder content in production code
- Components MUST render real data using real sub-components — never placeholder `<div>`s with "coming soon" text
- If seed data exists for an entity, use it. If not, show proper empty state (icon + message + action)
- Product grids, story lists, featured sections MUST use actual ProductCard/StoryCard components, not hardcoded divs
- Navigation links MUST point to existing routes — broken links (404) are gate failures

### REQ-UI-SLUG-ENCODING: Slugs must be ASCII-safe
- Generated slugs MUST strip or transliterate accented characters (é→e, á→a, ö→o, ü→u, etc.)
- Reason: URL encoding of accented characters doesn't match DB lookup — causes 404 on direct navigation
- Apply during seed data generation and any user-generated slug creation
- Add to `data-model.md` or `functional-conventions.md`

### REQ-UI-FILTER-ENCODING: URL filter values must handle special characters
- When filter values can contain commas (e.g., "Ethiopia, Yirgacheffe"), the delimiter between filter values MUST be pipe (`|`) not comma (`,`)
- Alternative: URL-encode individual values before joining
- Add to `functional-conventions.md`

### REQ-UI-RENDER-CONSISTENCY: Saved/cached views must use same components as live views
- When a page displays saved/cached data that has the same shape as live data, it MUST use the same rendering components
- Example: saved recipe detail must use DeviceCard, StepTimeline, CollapsibleSection — not raw JSON dump
- This prevents: raw JSON rendering, missing formatting, inconsistent UX between live and saved views

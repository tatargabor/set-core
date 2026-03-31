# Spec: Design Dispatch Context

## Status: modified

## Requirements

### REQ-DISPATCH-FALLBACK: Use design-system.md as primary design source
- `design_context_for_dispatch()` in `bridge.sh` SHALL check for `docs/design-system.md` first
- If `design-system.md` exists and contains `## Design Tokens` section, use it instead of `design-snapshot.md`
- Fallback chain: `docs/design-system.md` → `design-snapshot.md` → `figma-raw/sources/*tokens*.md` → empty

### REQ-DISPATCH-PAGE-MATCH: Page-specific design injection
- When `design-system.md` has `## Page Layouts` with named subsections (e.g., `### Homepage`, `### Catalog`), match the scope text against page names
- If scope mentions "homepage" or "landing" → inject the `### Homepage` subsection
- If scope mentions "catalog" or "product list" → inject `### Catalog`
- Always include the `## Design Tokens` section (colors, fonts, spacing) regardless of page match
- Max output: 200 lines (tokens + matched page section)

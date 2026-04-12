# Spec: Design Dispatch Context (delta)

## MODIFIED Requirements

### REQ-DISPATCH-FALLBACK: Use design-system.md as primary design source
- `design_context_for_dispatch()` in `bridge.sh` SHALL check for `docs/design-system.md` first
- If `design-system.md` exists and contains `## Design Tokens` section, use it instead of `design-snapshot.md`
- Fallback chain: `docs/design-system.md` → `design-snapshot.md` → `figma-raw/sources/*tokens*.md` → empty
- **NEW**: When `design-brief.md` exists, the function SHALL also read it for page-specific visual descriptions
- **NEW**: The function SHALL write a per-change `design.md` file instead of returning inline content when `design-brief.md` is present

#### Scenario: design-brief.md present alongside design-system.md
- **WHEN** `design_context_for_dispatch()` is called
- **AND** both `design-system.md` and `design-brief.md` exist
- **THEN** Design Tokens are extracted from `design-system.md` (always included)
- **AND** page-specific visual descriptions are extracted from `design-brief.md` (scope-matched)
- **AND** a combined `design.md` file is written to the change directory

#### Scenario: Only design-system.md present (backwards compatible)
- **WHEN** `design_context_for_dispatch()` is called
- **AND** `design-system.md` exists but `design-brief.md` does not
- **THEN** the existing behavior is preserved: tokens + matched Page Layouts + Components are returned inline
- **AND** max output remains 200 lines

### REQ-DISPATCH-PAGE-MATCH: Page-specific design injection
- When `design-system.md` has `## Page Layouts` with named subsections (e.g., `### Homepage`, `### Catalog`), match the scope text against page names
- **NEW**: When `design-brief.md` has `## Page: <name>` sections, match using precise page-name and alias matching
- **NEW**: Page matching uses phrase-level aliases (e.g., "hero banner", "product detail") instead of single-word matching to reduce false positives
- Always include the `## Design Tokens` section (colors, fonts, spacing) regardless of page match
- **CHANGED**: Max output limit does not apply to per-change design.md files (only applies to inline fallback)

#### Scenario: Precise matching with design-brief.md
- **WHEN** `design-brief.md` contains `## Page: Home` and `## Page: AdminProducts`
- **AND** the scope text is "Homepage hero banner featured products grid catalog detail"
- **THEN** the `## Page: Home` section is matched (via "homepage" and "hero banner" aliases)
- **AND** the `## Page: ProductCatalog` section is matched (via "catalog")
- **AND** `## Page: AdminProducts` is NOT matched (no specific admin alias in scope)

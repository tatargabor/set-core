# design-shell-autodetect Specification

## Purpose
TBD - created by archiving change design-binding-completeness. Update Purpose after archive.
## Requirements
### Requirement: Shell auto-detect via page-import scan
The manifest generator SHALL scan every `app/**/page.tsx` (and `app/**/layout.tsx`) in the design source for `import` statements pointing to `@/components/<name>` or relative `../components/<name>`. Components with ≥2 distinct importer pages SHALL be auto-added to `manifest.shared`.

#### Scenario: search-palette appears in 5 pages
- **GIVEN** `v0-export/app/{kavek,kereses,sztorik,kosar,fiokom}/page.tsx` import `SearchPalette` from `@/components/search-palette`
- **WHEN** the manifest is regenerated
- **THEN** `manifest.shared` contains `v0-export/components/search-palette.tsx`

#### Scenario: Single-importer component is NOT shared
- **GIVEN** only `v0-export/app/kosar/page.tsx` imports `OrderSummary` from `@/components/order-summary`
- **WHEN** the manifest is regenerated
- **THEN** `manifest.shared` does NOT contain `order-summary.tsx`
- **AND** the component appears as `component_deps` of the `/kosar` route only

#### Scenario: Hardcoded SHARED_GLOBS baseline preserved
- **GIVEN** `SHARED_GLOBS` baseline includes `app/layout.tsx` and `app/globals.css`
- **WHEN** auto-detect runs (regardless of import count)
- **THEN** these files remain in `manifest.shared`

#### Scenario: Both static and dynamic-only patterns
- **GIVEN** `app/some/page.tsx` uses `import dynamic from 'next/dynamic'` and `const X = dynamic(() => import('@/components/x'))`
- **WHEN** the v1 scanner runs
- **THEN** `x.tsx` is NOT detected as imported (v1 limitation; logged INFO for visibility)

### Requirement: Re-running set-design-import refreshes shared list
The `set-design-import --regenerate-manifest` flag SHALL trigger a re-scan and produce a manifest with the up-to-date shared list. Existing `manifest.shared_aliases` and `manifest.deferred_design_routes` SHALL be preserved across regenerations.

#### Scenario: New shell added in v0 source
- **GIVEN** an operator adds a new `wishlist-tray.tsx` component to v0-design and 3 pages start importing it
- **WHEN** the operator runs `set-design-import --regenerate-manifest`
- **THEN** the manifest's `shared` list now includes `wishlist-tray.tsx`

#### Scenario: Shared aliases preserved
- **GIVEN** `manifest.shared_aliases` has `{old-name: new-name}` mapping
- **WHEN** regenerate runs
- **THEN** the aliases are preserved verbatim


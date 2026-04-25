## ADDED Requirements

## IN SCOPE
- Per-change `design_components: list[str]` field in orchestration plan output (extends existing `design_routes`).
- Spec entity-reference syntax: `@component:NAME` and `@route:/PATH` markers in spec.md and linked feature spec files.
- Decompose-time extraction of entity references; manifest-validated.
- Dispatcher autopopulates `Focus files for this change` in `input.md` from `design_components`.

## OUT OF SCOPE
- Replacement of `design_routes` (it remains as the route-level binding).
- LLM-based fuzzy matching of spec content to design entities (markers are explicit).
- Implementation-side enforcement that agent's TSX code imports the bound components (covered by `design-shell-shadow-detection`).

### Requirement: Per-change design_components binding
The orchestration plan output (`orchestration-plan.json`) SHALL support a `design_components: list[str]` field per change containing absolute paths to design source TSX files (e.g., `v0-export/components/search-palette.tsx`) the change must mount.

#### Scenario: Field populated from manifest + entity refs
- **WHEN** decompose generates a plan AND the change has spec text containing `@component:search-palette`
- **AND** the manifest has `search-palette.tsx` in `shared`
- **THEN** the change's `design_components` list contains `v0-export/components/search-palette.tsx`

#### Scenario: Field populated from route component_deps
- **WHEN** decompose generates a plan AND the change has `design_routes: ["/kereses"]`
- **AND** the manifest's `/kereses` route entry has `component_deps: [v0-export/components/product-card.tsx]`
- **THEN** the change's `design_components` list includes `v0-export/components/product-card.tsx`

#### Scenario: Backward compat — empty field
- **WHEN** an older plan was generated without `design_components`
- **THEN** the dispatcher reads with `change.design_components or []`
- **AND** does NOT error on the missing field

### Requirement: Spec entity-reference marker syntax
Spec.md and linked feature spec files SHALL support inline `@component:NAME` and `@route:/PATH` markers within prose content. Markers reference design entities for explicit binding.

The parser SHALL extract:
- `@component:([a-z][a-z0-9-]+)` — component reference (matches manifest `shared` entries by base filename)
- `@route:(/\S+)` — route reference (matches manifest `routes[].path`)

#### Scenario: Marker extraction from spec
- **GIVEN** a spec section contains `Users open @component:search-palette to find products`
- **WHEN** the parser extracts entity references
- **THEN** the result includes `("component", "search-palette")`

#### Scenario: Manifest validation
- **WHEN** decompose extracts `@component:search-foo` from a spec
- **AND** the manifest has no shell named `search-foo`
- **THEN** decompose emits a `design_gap` ambiguity referencing the spec line and suggesting valid alternatives from manifest

#### Scenario: Multiple references in one spec
- **WHEN** a spec contains `@component:site-header`, `@component:search-palette`, and `@route:/kereses`
- **THEN** the change's `design_components` includes both component paths AND `design_routes` includes `/kereses`

### Requirement: Dispatcher injects design_components into input.md
The dispatcher SHALL write the `design_components` list into the agent's `input.md` under the `## Focus files for this change` section, prefixed with a directive line instructing the agent to consult these files first.

#### Scenario: Focus files contain bound components
- **WHEN** dispatcher writes `input.md` for a change with `design_components: ["v0-export/components/search-palette.tsx", "v0-export/components/site-header.tsx"]`
- **THEN** the input.md `## Focus files for this change` section contains both paths
- **AND** a directive line: "Mount these components from the design source. Do NOT create parallel implementations."

#### Scenario: Empty design_components produces no Focus mention
- **WHEN** a change has `design_components: []` (no UI)
- **THEN** the input.md does not include a Focus files section (or includes only non-design Focus entries from existing logic)

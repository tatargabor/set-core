# decompose-design-binding Specification

## Purpose
TBD - created by archiving change design-binding-completeness. Update Purpose after archive.
## Requirements
### Requirement: Plan output includes design_components per change
The `decompose` skill SHALL populate a `design_components: list[str]` field per change in `orchestration-plan.json`. The list is computed as the union of:
1. `component_deps` from each route in the change's `design_routes` (as listed in `manifest.routes[].component_deps`)
2. `manifest.shared` (auto-expanded shell components)
3. Components extracted from `@component:NAME` markers found in the change's spec subset (resolved against `manifest.shared` for full path)

The field is additive to the existing `design_routes` and does NOT replace it.

#### Scenario: Design components computed from routes
- **WHEN** decompose creates a change with `design_routes: ["/kereses"]`
- **AND** `manifest.routes[/kereses].component_deps: ["v0-export/components/product-card.tsx"]`
- **THEN** the change's `design_components` contains `v0-export/components/product-card.tsx`

#### Scenario: Entity markers contribute to design_components
- **GIVEN** a feature spec contains `Users open @component:search-palette to search`
- **WHEN** decompose processes the change for that spec
- **THEN** `design_components` includes the resolved path: `v0-export/components/search-palette.tsx`

#### Scenario: Backward compat
- **GIVEN** an older orchestration plan was generated without `design_components`
- **WHEN** the dispatcher reads it
- **THEN** the dispatcher treats `change.design_components` as `[]` and proceeds (no error)


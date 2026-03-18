# Spec: digest-multi-expand

## ADDED Requirements

## IN SCOPE
- Multi-select expansion in OverviewPanel and RequirementsPanel
- Expand All / Collapse All buttons in both panels
- Preserving existing click-to-toggle behavior per row

## OUT OF SCOPE
- Changes to DependencyTree or GroupsView (already uses Set<string>)
- Persisting expansion state across tab switches or page reloads
- Keyboard navigation for expand/collapse

### Requirement: Multi-select expansion

The OverviewPanel and RequirementsPanel SHALL allow multiple requirement rows to be expanded simultaneously.

#### Scenario: Open multiple rows
- **WHEN** user clicks on requirement row A to expand it, then clicks on requirement row B
- **THEN** both row A and row B remain expanded

#### Scenario: Toggle individual row
- **WHEN** user clicks on an already-expanded requirement row
- **THEN** that row collapses while other expanded rows remain open

### Requirement: Expand All and Collapse All controls

Both OverviewPanel and RequirementsPanel SHALL provide Expand All and Collapse All buttons.

#### Scenario: Expand All
- **WHEN** user clicks "Expand All"
- **THEN** all requirement rows that have acceptance criteria are expanded

#### Scenario: Collapse All
- **WHEN** user clicks "Collapse All"
- **THEN** all expanded requirement rows are collapsed

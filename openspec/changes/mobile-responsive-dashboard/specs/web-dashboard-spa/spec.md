## MODIFIED Requirements

### Requirement: Responsive layout
The dashboard SHALL use a two-panel layout: change table (upper) and log viewer (lower), with a resizable split. The log panel SHALL be collapsible. On viewports below 768px, the two-panel split SHALL be replaced with stacked panels and the sidebar SHALL convert to an overlay drawer. All interactive elements SHALL meet a 44px minimum touch target on mobile viewports.

#### Scenario: Toggle log panel
- **WHEN** user clicks the log panel toggle
- **THEN** the log panel collapses and the change table takes full height (or vice versa)

#### Scenario: Mobile stacked layout
- **WHEN** viewport is below 768px
- **THEN** the split panel becomes stacked with a collapsible log bottom sheet

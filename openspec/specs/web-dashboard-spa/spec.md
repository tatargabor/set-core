## MODIFIED Requirements

### Requirement: Responsive layout
The dashboard SHALL use a two-panel layout: change table (upper) and log viewer (lower), with a resizable split. The log panel SHALL be collapsible. The dashboard navigation SHALL include tabs: Changes, Plan, Tokens, Requirements, Audit, Digest, Sessions, and **Orchestration**. The Orchestration tab SHALL render the orchestration chat component.

#### Scenario: Toggle log panel
- **WHEN** user clicks the log panel toggle
- **THEN** the log panel collapses and the change table takes full height (or vice versa)

#### Scenario: Navigate to Orchestration tab
- **WHEN** user clicks the "Orchestration" tab
- **THEN** the orchestration chat interface is rendered in the main content area with text input, optional voice input, and message history

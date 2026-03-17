## MODIFIED Requirements

### Requirement: Responsive layout
The dashboard SHALL use a two-panel layout: change table (upper) and log viewer (lower), with a resizable split. The log panel SHALL be collapsible. The dashboard navigation SHALL include tabs: Changes, Phases, Plan, Tokens, Requirements, Audit, Digest, Sessions, and Orchestration. The Digest tab SHALL include sub-tabs: Overview, Requirements, Domains, Triage, and **AC** (acceptance criteria cross-cutting view).

#### Scenario: Toggle log panel
- **WHEN** user clicks the log panel toggle
- **THEN** the log panel collapses and the change table takes full height (or vice versa)

#### Scenario: Navigate to Orchestration tab
- **WHEN** user clicks the "Orchestration" tab
- **THEN** the orchestration chat interface is rendered in the main content area with text input, optional voice input, and message history

#### Scenario: Navigate to AC sub-tab in Digest
- **WHEN** user is on the Digest tab and clicks the "AC" sub-tab
- **THEN** the cross-cutting acceptance criteria view renders with domain grouping and progress tracking

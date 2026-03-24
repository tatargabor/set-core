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
## MODIFIED Requirements

### Requirement: Visual phase timeline for changes
Each change displays a horizontal timeline bar showing its progression through orchestration phases.

#### Scenario: Running change timeline
- **WHEN** a change is in progress (running/verifying)
- **THEN** a horizontal bar shows completed phases in color and the current phase with a pulse animation
- **THEN** phases include: Dispatch → Implement → Build → Test → Review → Smoke → Merge

#### Scenario: Completed change timeline
- **WHEN** a change has status "done" or "merged"
- **THEN** all phases show as completed with their duration
- **THEN** failed-then-retried phases show the retry count

#### Scenario: Timeline data sources
- **WHEN** rendering the timeline
- **THEN** use `started_at`/`completed_at` for overall duration
- **THEN** use `gate_build_ms`, `gate_test_ms`, `gate_review_ms`, `gate_verify_ms` for gate phase durations
- **THEN** use `gate_total_ms` for total gate time

#### Scenario: Timeline in change detail
- **WHEN** a change row is expanded (via gate detail click or dedicated expand)
- **THEN** the timeline is shown at the top of the expanded area

#### Scenario: Detailed timeline view with state transitions
- **WHEN** the user navigates to the detailed timeline for a specific change
- **THEN** the view shows each state transition as a node in a horizontal flow with timestamps
- **AND** gate results are shown at each verify node
- **AND** failed transitions are highlighted with failure reason
- **AND** a summary line shows total duration, retry count, and gate run count

### Requirement: Manager overview page
The manager overview page at `/manager` SHALL display registered projects as clickable summary tiles that link to individual project detail pages.

#### Scenario: Tile displays summary
- **WHEN** the manager overview loads with registered projects
- **THEN** each tile shows project name, mode badge, sentinel status (running/idle), and if running: progress summary (e.g., "5/12 merged, 1.8M tokens")

#### Scenario: Tile links to detail
- **WHEN** user clicks a project tile
- **THEN** browser navigates to `/manager/:project` detail view

#### Scenario: No inline process controls on tiles
- **WHEN** the overview page renders
- **THEN** tiles do NOT contain Start/Stop/Restart buttons — process control lives in the detail view only

# Dashboard Unified Logs Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Gate outputs (Build, Test, E2E, Review, Smoke) as sub-tabs in the Log tab right pane
- Merge/archive event log as a sub-tab
- Remove standalone Gates tab from the detail panel
- Dynamic sub-tabs: only gates with results shown

### Out of scope
- Changing the Timeline tab
- Changing the left pane orchestration log
- New API endpoints
- Changing gate data storage or state format

## Requirements

### Requirement: Gate outputs as Log sub-tabs
The Log tab right pane SHALL display gate outputs as sub-tabs alongside the existing Task session tabs. Each gate with a result (Build, Test, E2E, Review, Smoke) SHALL appear as its own sub-tab showing status badge, timing, and full output text.

#### Scenario: Change with gate results
- **WHEN** a change has `build_result`, `test_result`, or `e2e_result` set
- **THEN** corresponding sub-tabs (Build, Test, E2E) appear in the Log tab right pane tab bar
- **AND** each sub-tab shows the gate's result badge (pass/fail/skip), execution time, and full output

#### Scenario: Change with no gate results
- **WHEN** a change has no gate results (all gates pending)
- **THEN** only the Task sub-tab appears
- **AND** no empty gate tabs are shown

#### Scenario: Gate sub-tab content format
- **WHEN** user clicks a gate sub-tab (e.g., Build)
- **THEN** the pane shows: result status badge at top, execution time, and scrollable output text below
- **AND** output text uses the same monospace styling as task session logs

### Requirement: Remove standalone Gates tab
The Gates tab SHALL be removed from the detail panel tab bar. The detail panel SHALL have 2 tabs: Log and Timeline.

#### Scenario: Tab bar after change
- **WHEN** the detail panel renders
- **THEN** tab bar shows only "Log" and "Timeline"
- **AND** "Gates" tab is not present

### Requirement: Merge event log sub-tab
The Log tab SHALL include a Merge sub-tab showing merge-related events for the selected change, extracted from the orchestration log lines.

#### Scenario: Change with merge events
- **WHEN** a change has been merged (status "merged")
- **THEN** the Merge sub-tab appears showing merge-related log lines (MERGE, ARCHIVE events) filtered to this change

#### Scenario: Change not yet merged
- **WHEN** a change has not been merged
- **THEN** the Merge sub-tab does not appear

### Requirement: Task sub-tab is default
The Task sub-tab SHALL be selected by default when a change is selected. If the change has a failing gate, the failing gate's sub-tab SHALL be auto-selected instead.

#### Scenario: Default selection — no failures
- **WHEN** user selects a change with all gates passing or pending
- **THEN** Task sub-tab is selected by default

#### Scenario: Default selection — gate failure
- **WHEN** user selects a change with a failing gate (e.g., e2e_result=fail)
- **THEN** the first failing gate's sub-tab is auto-selected

# Gate History View Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Bottom-panel Session tab rename
The LogPanel SHALL display the bottom-panel session log tab with the label "Session" instead of "Task".

#### Scenario: Panel renders
- **WHEN** a user opens a change in the dashboard
- **THEN** the bottom-panel tab previously labeled "Task" is now labeled "Session"
- **THEN** the tab's content (session picker + parsed JSONL log) is unchanged
- **THEN** the internal tab id remains stable so URL state and keyboard shortcuts continue to work

### Requirement: Gate history sub-tabs from journal
The LogPanel SHALL render per-run sub-tabs under each gate tab (Build, Test, E2E, Review, Smoke) when the journal contains run history for that gate.

#### Scenario: Journal has multiple runs for a gate
- **WHEN** the user selects the E2E gate tab for a change with 3 runs recorded in the journal
- **THEN** a secondary sub-tab row appears above the gate output pane with buttons `[Run 1 ✗] [Run 2 ✗] [Run 3 ✓]`
- **THEN** each sub-tab shows a pass/fail/skip glyph matching that run's result
- **THEN** the latest run is selected by default
- **THEN** the `GateOutputPane` renders the selected run's output, result, and duration

#### Scenario: Switching between runs
- **WHEN** the user clicks a non-selected run sub-tab
- **THEN** the `GateOutputPane` updates to show that run's output, result, and duration without refetching data
- **THEN** the previously selected sub-tab becomes unselected
- **THEN** no page navigation or URL change occurs

#### Scenario: Gate has only one run
- **WHEN** the user selects a gate tab for a change with exactly one recorded run
- **THEN** a single sub-tab appears showing the run
- **THEN** the output pane renders that run
- **THEN** the sub-tab row still appears (consistent UI) but with only one button

#### Scenario: Gate has no journal entries (legacy change)
- **WHEN** the user selects a gate tab for a change whose journal file is missing or empty
- **THEN** no sub-tab row is rendered
- **THEN** the `GateOutputPane` falls back to reading `build_result`/`build_output`/`gate_build_ms` (etc.) from the `ChangeInfo` object as today
- **THEN** the legacy single-run display is preserved exactly as it works now

### Requirement: Journal fetcher in web API client
The web dashboard SHALL provide a typed API client function `getChangeJournal(project, name)` that returns the journal response.

#### Scenario: Fetcher signature and types
- **WHEN** a developer imports `getChangeJournal` from `web/src/lib/api.ts`
- **THEN** its return type is `Promise<{ entries: JournalEntry[]; grouped: Record<string, GateRun[]> }>`
- **THEN** `JournalEntry` has `ts: string`, `field: string`, `old: unknown`, `new: unknown`, `seq: number`
- **THEN** `GateRun` has `run: number`, `result: "pass" | "fail" | "skip"`, `output?: string`, `ts: string`, `ms: number`

#### Scenario: Journal fetch error
- **WHEN** the backend returns HTTP 404 or 500 for the journal endpoint
- **THEN** the fetcher rejects with an Error whose message includes the change name
- **THEN** the LogPanel component catches the error and falls back to the legacy single-run view

### Requirement: E2E test coverage
The change SHALL include a Playwright E2E test verifying the gate history sub-tabs behave correctly across journal-present and legacy scenarios.

#### Scenario: Test asserts sub-tab rendering with history
- **WHEN** the Playwright test visits a change whose journal has 3 e2e runs
- **THEN** the test asserts that three sub-tab buttons are visible under the E2E tab
- **THEN** the test clicks the second sub-tab and asserts the output pane shows the second run's content
- **THEN** the test passes

#### Scenario: Test asserts legacy fallback
- **WHEN** the Playwright test visits a change whose journal is empty or missing
- **THEN** the test asserts no sub-tab row is rendered under the gate tabs
- **THEN** the test asserts the gate output pane shows the legacy single-run content from `ChangeInfo`
- **THEN** the test passes

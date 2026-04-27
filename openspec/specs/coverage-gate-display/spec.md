# Coverage Gate Display Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Display spec_coverage_result as a gate badge in GateBar
- Show spec coverage details in GateDetail expandable section
- API endpoint to serve spec-coverage-report.md
- Coverage report viewer panel/tab in the dashboard
- Use coverage-merged.json for accurate coverage counts in DigestView overview

### Out of scope
- Modifying the verifier or planner backend logic
- Generating or regenerating coverage reports from the frontend
- Editing coverage data from the UI

## Requirements

### Requirement: ChangeInfo type includes spec_coverage_result
The frontend `ChangeInfo` TypeScript interface SHALL include `spec_coverage_result` as an optional string field (values: "pass", "fail", "timeout", or absent).

#### Scenario: spec_coverage_result present in state
- **WHEN** the state API returns a change with `spec_coverage_result: "pass"`
- **THEN** the ChangeInfo object SHALL have `spec_coverage_result` set to `"pass"`

#### Scenario: spec_coverage_result absent
- **WHEN** the state API returns a change without spec_coverage_result
- **THEN** the field SHALL be undefined (gate not shown)

### Requirement: Spec coverage gate badge in GateBar
GateBar SHALL render a 5th gate badge labeled "SC" (Spec Coverage) when `spec_coverage_result` is present on a change. The badge SHALL use the same pass/fail/skip styling as existing gates.

#### Scenario: SC badge shows pass
- **WHEN** a change has `spec_coverage_result: "pass"`
- **THEN** GateBar renders an "SC" badge with green pass styling

#### Scenario: SC badge shows fail
- **WHEN** a change has `spec_coverage_result: "fail"` or `"timeout"`
- **THEN** GateBar renders an "SC" badge with red fail styling

#### Scenario: SC badge hidden when absent
- **WHEN** a change has no spec_coverage_result
- **THEN** no SC badge renders (consistent with other gates)

### Requirement: Spec coverage in GateDetail
GateDetail SHALL include a "Spec Coverage" expandable section when `spec_coverage_result` is present. The section SHALL show the result and, if available, the coverage report content.

#### Scenario: Expand spec coverage gate detail
- **WHEN** user expands the GateDetail for a change with spec_coverage_result
- **THEN** a "Spec Coverage" section appears showing the result status
- **AND** if coverage report content is available, it renders as formatted text

### Requirement: Coverage report API endpoint
The API SHALL expose `GET /api/{project}/coverage-report` which returns the content of `set/orchestration/spec-coverage-report.md`. If the file does not exist, return `{"exists": false}`.

#### Scenario: Report exists
- **WHEN** `spec-coverage-report.md` exists in the project's orchestration directory
- **THEN** the endpoint returns `{"exists": true, "content": "<markdown content>"}`

#### Scenario: Report missing
- **WHEN** `spec-coverage-report.md` does not exist
- **THEN** the endpoint returns `{"exists": false}`

### Requirement: Coverage report viewer
The dashboard SHALL provide a way to view the spec coverage report. This SHALL be accessible as a sub-panel or section within the existing Digest or Requirements view.

#### Scenario: View coverage report
- **WHEN** user navigates to the coverage report viewer and a report exists
- **THEN** the markdown content renders using the existing MarkdownPanel component

#### Scenario: No report available
- **WHEN** the coverage report does not exist
- **THEN** the viewer shows "No coverage report generated yet"

### Requirement: Coverage-merged data in DigestView overview
The DigestView overview panel SHALL prefer `coverage-merged.json` over `coverage.json` when available, as it contains accumulated coverage across multiple orchestration cycles.

#### Scenario: Merged coverage available
- **WHEN** the digest API returns both `coverage` and `coverage_merged` objects
- **THEN** the overview panel uses `coverage_merged.coverage` for status counts and progress bar

#### Scenario: Only base coverage available
- **WHEN** the digest API returns `coverage` but no `coverage_merged`
- **THEN** the overview panel falls back to `coverage.coverage` (current behavior)

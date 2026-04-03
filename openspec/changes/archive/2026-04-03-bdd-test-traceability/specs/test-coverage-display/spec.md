## ADDED Requirements

## IN SCOPE
- AC panel progressive disclosure: domain → REQ → scenario → test (4 levels, each expandable)
- Coverage summary bar at top of AC panel
- Risk level and test status badges (compact, inline)
- Report.html test coverage section (table, not tree)
- Graceful handling when no coverage data exists

## OUT OF SCOPE
- New standalone tab or page (extend existing AC panel only)
- Interactive test re-run from UI
- Test history across runs (only current run)
- Detailed test output/logs/screenshots in AC panel (gate detail view handles this)
- Changing the Reqs tab or Domains tab (AC tab only)

### Requirement: AC panel uses progressive disclosure for scenarios and tests
The AC panel SHALL organize data in 4 collapsible levels to prevent information overload. Each level only expands when the user clicks.

#### Scenario: Level 1 — Domain rows (default view)
- **WHEN** the AC panel loads
- **THEN** it SHALL show one row per domain with: domain name, REQ count, coverage fraction (e.g., "6/7"), and a status indicator (all-pass/has-gaps/no-data)
- **AND** all domains SHALL be collapsed by default
- **AND** a coverage summary bar SHALL appear at the top (covered/total, percentage, color bar)

#### Scenario: Level 2 — REQ rows (domain expanded)
- **WHEN** the user clicks a domain row
- **THEN** it SHALL expand to show one row per REQ with: REQ ID, title, change name, change status, scenario count with test fraction (e.g., "3/3"), and pass/fail indicator
- **AND** REQs with coverage gaps SHALL sort first with a visual highlight

#### Scenario: Level 3 — Scenario rows (REQ expanded)
- **WHEN** the user clicks a REQ row
- **THEN** it SHALL expand to show one row per scenario with: scenario name, risk badge (HIGH=red, MEDIUM=yellow, LOW=gray), test status (pass/fail/no-test), and WHEN/THEN text
- **AND** WHEN/THEN text SHALL be shown in a compact format (smaller font, muted color)

#### Scenario: Level 4 — Test detail (scenario with test)
- **WHEN** a scenario has a matching test case
- **THEN** the scenario row SHALL show: test file name and test name inline, result icon, and duration if available
- **AND** this detail SHALL be visible without further expansion (inline with scenario row)

### Requirement: Coverage summary bar at top of AC panel
The AC panel SHALL show a coverage summary bar at the top when test coverage data exists.

#### Scenario: Coverage summary with data
- **WHEN** test_coverage data is available in state
- **THEN** the panel SHALL show: covered count, total count, percentage, non-testable count, and a TuiProgress-style bar
- **AND** the bar color SHALL be green (>=90%), yellow (>=70%), or red (<70%)

#### Scenario: No coverage data
- **WHEN** test_coverage data is not available
- **THEN** the AC panel SHALL behave exactly as it does today (plain AC checkboxes)
- **AND** no coverage summary bar SHALL appear

### Requirement: AC panel backward compatible without scenarios
When a digest does not contain parsed scenarios (older format or specs without WHEN/THEN), the AC panel SHALL fall back to the current behavior.

#### Scenario: Requirements with acceptance_criteria but no scenarios
- **WHEN** a requirement has `acceptance_criteria` strings but empty `scenarios` array
- **THEN** the panel SHALL render the plain checkbox list as it does today
- **AND** no scenario expansion level SHALL appear for that requirement

### Requirement: Risk level badges on scenarios
Each scenario SHALL display its risk level as a compact inline badge.

#### Scenario: Badge rendering
- **WHEN** a scenario has a risk level from the test plan
- **THEN** a small badge SHALL appear next to the scenario name: "H" (red), "M" (yellow), "L" (gray)
- **AND** the badge SHALL be minimal (2-3 chars, small font, rounded) to avoid visual clutter

### Requirement: Report includes test coverage section
The HTML report SHALL include a test coverage section after the execution table.

#### Scenario: Report with coverage data
- **WHEN** the report is generated and test_coverage exists in state
- **THEN** it SHALL render a "Test Coverage" section with:
  - Coverage summary: percentage bar, covered/total, gap count
  - Table: REQ ID | Name | Domain | Scenarios | Tests | Pass/Fail
  - Rows sorted: gaps first (red bg), then failed, then passed

#### Scenario: Report without coverage data
- **WHEN** the report is generated and no test_coverage exists
- **THEN** the "Test Coverage" section SHALL show "No acceptance test data available"

#### Scenario: Coverage gaps highlighted
- **WHEN** a requirement has zero test coverage and is not non-testable
- **THEN** its row SHALL have class `gap-critical` (red background tint)

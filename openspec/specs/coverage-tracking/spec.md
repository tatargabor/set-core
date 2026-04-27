# Coverage Tracking Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Planner populates coverage mapping
The planner SHALL include `spec_files[]` and `requirements[]` arrays in each change entry of `orchestration-plan.json`. After plan generation, the system SHALL write `coverage.json` mapping every requirement to its assigned change.

#### Scenario: Plan output includes requirement mapping
- **WHEN** planner generates a plan from a digest
- **THEN** each change in `orchestration-plan.json` has `spec_files` (list of raw spec file paths relative to spec base dir), `requirements` (list of REQ-* IDs the change owns), and optionally `also_affects_reqs` (list of cross-cutting REQ-* IDs the change must incorporate)

#### Scenario: Coverage file populated after planning
- **WHEN** plan generation completes
- **THEN** `set/orchestration/digest/coverage.json` is updated with every requirement mapped to its change, status `planned`
- **AND** cross-cutting requirements include `also_affects` listing other changes that must incorporate them

#### Scenario: Plan validation checks new fields
- **WHEN** `validate_plan()` runs on a digest-mode plan
- **THEN** it validates that `spec_files` entries are non-empty arrays, `requirements` entries reference IDs that exist in `requirements.json`, and `also_affects_reqs` entries (if present) reference valid cross-cutting REQ-* IDs that have a primary owner in another change

#### Scenario: Cross-cutting requirement has primary owner
- **WHEN** a cross-cutting requirement like `REQ-I18N-001` exists
- **THEN** exactly one change lists it in `requirements[]` (primary owner)
- **AND** other changes that must incorporate it list it in `also_affects_reqs[]`
- **AND** `coverage.json` entry includes `also_affects` with those change names

### Requirement: Coverage gap detection
The system SHALL detect requirements from `requirements.json` that are not covered by any change in the plan.

#### Scenario: All requirements covered
- **WHEN** every non-removed REQ-* ID in requirements.json appears in at least one change's `requirements[]`
- **THEN** `coverage.json` has `uncovered: []` and the system reports "Full coverage"

#### Scenario: Uncovered requirements detected
- **WHEN** REQ-SUB-003 exists in requirements.json but no change lists it in `requirements[]`
- **THEN** `coverage.json` has `uncovered: ["REQ-SUB-003"]`
- **AND** the system prints a warning: "Warning: 1 uncovered requirement(s): REQ-SUB-003"

### Requirement: Coverage status lifecycle
Coverage status for each requirement SHALL track the implementation lifecycle: `planned` → `dispatched` → `running` → `merged`. Each transition is triggered by an explicit `update_coverage_status()` call at the corresponding hook site.

#### Scenario: Status updates to dispatched
- **WHEN** orchestrator dispatches the `cart-feature` change via `dispatch_change()` in `dispatcher.sh`
- **THEN** all requirements mapped to `cart-feature` in coverage.json update to `status: dispatched`

#### Scenario: Status updates to running
- **WHEN** the monitor in `monitor.sh` detects that the `cart-feature` change loop has started producing commits
- **THEN** all requirements mapped to `cart-feature` in coverage.json update to `status: running`

#### Scenario: Status reaches merged
- **WHEN** `cart-feature` is successfully merged via the merge handler
- **THEN** all its requirements in coverage.json update to `status: merged`

### Requirement: Coverage report command
`set-orchestrate coverage` SHALL display a human-readable coverage report showing requirement status grouped by domain.

#### Scenario: Coverage report output
- **WHEN** user runs `set-orchestrate coverage`
- **THEN** output shows per-domain breakdown: total requirements, planned/dispatched/running/merged counts, and lists any uncovered requirements

#### Scenario: Coverage report with no digest
- **WHEN** user runs `set-orchestrate coverage` but no digest exists
- **THEN** the system prints "No digest found. Run `set-orchestrate digest --spec <path>` first."

#### Scenario: Coverage report with digest but no plan
- **WHEN** user runs `set-orchestrate coverage` and `requirements.json` exists but `coverage.json` is empty
- **THEN** the system prints the total requirement count per domain and "No plan generated yet. All requirements uncovered."

#### Scenario: Orphaned coverage entries
- **WHEN** a requirement was removed on re-digest (`status: removed` in requirements.json) but coverage.json still references it
- **THEN** the coverage report shows it in an "Orphaned" section with a note to reconcile

### Requirement: Planner prompt includes coverage context on replan
When replanning (auto_replan or manual replan), the planner prompt SHALL include the current coverage status so that already-covered requirements are not re-planned.

#### Scenario: Replan skips merged requirements
- **WHEN** auto-replan triggers after some changes are merged
- **THEN** the planner prompt includes "Already covered (merged): REQ-CART-001, REQ-CART-002"
- **AND** the planner prompt includes "Already covered (running): REQ-SUB-001"

#### Scenario: Replan in digest mode uses auto_replan_cycle
- **WHEN** `auto_replan_cycle()` in `planner.sh` runs with `INPUT_MODE="digest"`
- **THEN** it restores digest mode correctly (not falling back to spec/brief mode)

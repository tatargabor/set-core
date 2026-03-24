## ADDED Requirements

### Requirement: Post-planning generates spec coverage report
After `validate_plan()` succeeds, the planner SHALL generate a spec coverage annotation report that marks each digest requirement as covered, deferred, or uncovered relative to the plan's change assignments.

#### Scenario: All requirements covered by changes
- **WHEN** every digest requirement appears in at least one change's `requirements[]` or `also_affects_reqs[]`
- **THEN** the coverage report SHALL mark each requirement as `[COVERED by <change-name>]`
- **AND** the report SHALL be written to `set/orchestration/spec-coverage-report.md`

#### Scenario: Some requirements deferred
- **WHEN** a requirement is not assigned to any change but appears in `deferred_requirements[]`
- **THEN** the coverage report SHALL mark it as `[DEFERRED: <reason>]`

#### Scenario: Uncovered requirements present
- **WHEN** a requirement is not assigned to any change and not deferred
- **THEN** the coverage report SHALL mark it as `[UNCOVERED]`
- **AND** this condition SHALL already be caught as an error by `validate_plan()` (from spec-implementation-fidelity)

#### Scenario: No digest directory available
- **WHEN** `validate_plan()` runs without a digest directory
- **THEN** the coverage report SHALL NOT be generated
- **AND** no error SHALL be raised

### Requirement: Coverage report is human-readable with per-requirement detail
The coverage report SHALL list each requirement with its coverage status, the covering change name(s), and the requirement's title from the digest. The format SHALL be a markdown table for easy scanning.

#### Scenario: Report format includes requirement details
- **WHEN** the coverage report is generated
- **THEN** it SHALL include a markdown table with columns: Requirement ID, Title, Status, Change(s)
- **AND** it SHALL include a summary line: "N/M requirements covered, K deferred, J uncovered"

#### Scenario: Report is regenerated on replan
- **WHEN** a replan occurs (new plan generated after a failed cycle)
- **THEN** the coverage report SHALL be regenerated with the new plan's assignments
- **AND** the previous report SHALL be overwritten

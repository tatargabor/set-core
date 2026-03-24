## MODIFIED Requirements

### Requirement: Spec coverage report generation
`generate_coverage_report()` SHALL produce a markdown report mapping requirements (or source items) to changes with their current lifecycle status. The report SHALL be regenerated at orchestration terminal state to reflect final statuses.

#### Scenario: State-aware report in digest mode
- **WHEN** `generate_coverage_report()` is called with a `state_file` parameter
- **THEN** each requirement's status SHALL reflect the owning change's status from state: MERGED, DISPATCHED, FAILED, or PENDING
- **AND** the status SHALL replace the static COVERED label used at plan validation time
- **AND** DEFERRED and UNCOVERED items SHALL remain unchanged (they have no owning change)

#### Scenario: Report from source items in single-file mode
- **WHEN** `generate_coverage_report()` is called without `digest_dir` but with a plan containing `source_items`
- **THEN** the report SHALL render source items instead of digest requirements
- **AND** each source item SHALL show its assigned change and that change's status
- **AND** items with `change: null` SHALL show as EXCLUDED

#### Scenario: Report regenerated at terminal state
- **WHEN** the orchestration reaches a terminal state (done, time_limit, total_failure, dep_blocked, replan_limit, replan_exhausted)
- **THEN** `_send_terminal_notifications()` SHALL call report regeneration before sending the summary email
- **AND** the regenerated report SHALL overwrite the initial plan-time report at `set/orchestration/spec-coverage-report.md`

#### Scenario: Backward compatibility when state_file is not provided
- **WHEN** `generate_coverage_report()` is called without `state_file` (e.g., during plan validation)
- **THEN** the function SHALL produce the existing static COVERED/DEFERRED/UNCOVERED report
- **AND** no error is raised

## IN SCOPE
- `generate_coverage_report()` state-aware rendering
- `generate_coverage_report()` single-file mode (source_items)
- Engine terminal state trigger for report regeneration
- Summary line with MERGED/FAILED/PENDING counts

## OUT OF SCOPE
- Per-merge incremental report updates (terminal regeneration is sufficient)
- Report format changes beyond status column (table structure stays the same)
- Email content changes (email already uses `final_coverage_check()` output)

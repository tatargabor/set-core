# Coverage Consistency Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: reconcile-coverage-on-completion
Before any terminal decision in `_check_completion()`, the engine must reconcile coverage.json with actual change statuses in the state file. This runs before all three exit paths (dep_blocked, total_failure, normal done/replan).

#### Scenario: merged change with non-merged coverage
- **WHEN** `_check_completion()` determines all changes are terminal AND coverage.json has requirements with status != "merged" whose owning change has status "merged" in state
- **THEN** coverage.json is updated: those requirements become "merged", coverage-merged.json is updated via read-merge-write (same pattern as `update_coverage_status()`), and a WARNING is logged with the count of reconciled requirements

#### Scenario: all coverage already consistent
- **WHEN** `_check_completion()` runs and all requirements in coverage.json already have status matching their change's state
- **THEN** no changes are made to coverage files, no warnings logged

### Requirement: reconcile-coverage-function
`digest.py` must expose a `reconcile_coverage(state_file, digest_dir)` function.

#### Scenario: basic reconciliation
- **WHEN** called with a state file where changes A, B are "merged" but coverage.json shows their requirements as "planned" or any other non-merged status
- **THEN** returns the count of fixed requirements, updates coverage.json in-place (using `cov_data.get("coverage", {})` pattern to unwrap the nested structure), merges into coverage-merged.json via read-merge-write

#### Scenario: no digest exists
- **WHEN** called but no coverage.json exists in digest_dir
- **THEN** returns 0, no error raised

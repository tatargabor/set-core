## ADDED Requirements

### Requirement: Phase 1b must not bypass pre-merge gates

Orphaned `integrating`-status changes SHALL be restored to the merge queue ONLY if all blocking pre-merge gate results on the change are present and non-failing. `integrating` is set by `_integrate_main_into_branch` at the start of the verify pipeline, BEFORE gates execute — so the presence of this status alone does NOT imply the change is ready to merge. Restoring an interrupted mid-pipeline change to the merge queue has been observed to cause the merger to merge changes whose pre-merge verdict (spec_verify, review, rules) was FAIL.

When Phase 1b encounters an `integrating`-status change whose gate results are incomplete or contain any `fail`/`critical` value, the change SHALL be reset to `status=running` with `ralph_pid=None`. This routes the change through the `_poll_active_changes` "dead agent with `loop_status=done`" recovery path, which re-enters `handle_change_done` and re-runs the full verify pipeline. Retry counters (`verify_retry_count`, `gate_retry_count`) SHALL NOT be incremented by this reset — a supervisor restart is an infrastructure event, not a gate failure.

#### Scenario: All pre-merge gates passed, merge_queue append lost to restart

- **GIVEN** a change with `status=integrating` and a worktree on disk
- **AND** the change has all 6 blocking gate results populated with non-fail values (`build_result`, `test_result`, `review_result`, `scope_check`, `e2e_result`, `spec_coverage_result` — each in `{pass, skipped, warn-fail}`)
- **WHEN** `_cleanup_orphans` runs at supervisor startup
- **THEN** the change name SHALL be appended to `state.merge_queue` (if not already present)
- **AND** the change's `status` SHALL remain `integrating`
- **AND** the change's `ralph_pid` SHALL NOT be modified by Phase 1b

#### Scenario: Verify pipeline interrupted mid-gate

- **GIVEN** a change with `status=integrating` and a worktree on disk
- **AND** at least one blocking gate result is `None` (gate did not complete before restart)
- **WHEN** `_cleanup_orphans` runs at supervisor startup
- **THEN** the change's `status` SHALL be set to `running`
- **AND** the change's `ralph_pid` SHALL be set to `None`
- **AND** the change SHALL NOT be appended to `state.merge_queue`
- **AND** `verify_retry_count` SHALL NOT be incremented
- **AND** a WARNING log line SHALL be emitted naming the change and noting the gates were incomplete

#### Scenario: spec_verify reported FAIL before interrupted restart

- **GIVEN** a change with `status=integrating` and a worktree on disk
- **AND** the change has `spec_coverage_result=fail` (spec_verify gate completed with a FAIL verdict that would normally trigger a retry dispatch)
- **WHEN** `_cleanup_orphans` runs at supervisor startup
- **THEN** the change's `status` SHALL be set to `running`
- **AND** the change SHALL NOT be appended to `state.merge_queue`
- **AND** the change SHALL re-enter the verify pipeline on the next poll cycle

#### Scenario: review gate reported FAIL before interrupted restart

- **GIVEN** a change with `status=integrating` and a worktree on disk
- **AND** the change has `review_result=fail`
- **WHEN** `_cleanup_orphans` runs at supervisor startup
- **THEN** the change's `status` SHALL be set to `running`
- **AND** the change SHALL NOT be appended to `state.merge_queue`

#### Scenario: Worktree missing (unchanged precondition)

- **GIVEN** a change with `status=integrating`
- **AND** its `worktree_path` does not exist on disk
- **WHEN** `_cleanup_orphans` runs at supervisor startup
- **THEN** the change SHALL NOT be appended to `state.merge_queue`
- **AND** the change's status SHALL NOT be modified by Phase 1b (stall handling is delegated to `_poll_active_changes`)

#### Scenario: Already queued (unchanged precondition)

- **GIVEN** a change with `status=integrating` that is already present in `state.merge_queue`
- **WHEN** `_cleanup_orphans` runs at supervisor startup
- **THEN** the change SHALL NOT be duplicated in `state.merge_queue`
- **AND** no status or PID reset SHALL occur (the change is already scheduled for merge)

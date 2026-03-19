## MODIFIED Requirements

### Requirement: VG-PIPELINE — Gate pipeline (handle_change_done)
Ordered steps: build → test → e2e → scope check → test file check → review → rules → verify → merge queue. Each gate step SHALL resolve a GateConfig via `resolve_gate_config()` at the start of the pipeline and use its `should_run()` and `is_blocking()` methods to determine execution. Gates with mode `"skip"` SHALL NOT execute and SHALL log "SKIPPED (gate_profile)". Gates with mode `"warn"` SHALL execute but failures SHALL NOT consume retry budget or block merge — they SHALL log a warning and continue. Gates with mode `"soft"` (spec_verify only) SHALL execute but failures SHALL be non-blocking if all other gates passed.

#### Scenario: Infrastructure change skips build/test/e2e
- **WHEN** a change with change_type `"infrastructure"` enters handle_change_done
- **THEN** the build, test, and e2e gate steps SHALL be skipped
- **AND** each SHALL log "Verify gate: <gate> SKIPPED for <name> (gate_profile)"
- **AND** scope_check, review, rules SHALL execute normally

#### Scenario: Feature change runs all gates
- **WHEN** a change with change_type `"feature"` enters handle_change_done
- **THEN** all gate steps SHALL execute with blocking behavior (identical to current behavior)

#### Scenario: Warn-mode test failure is non-blocking
- **WHEN** a schema change runs tests (gate mode `"warn"`) and tests fail
- **THEN** the failure SHALL be logged as a warning
- **AND** the verify_retry_count SHALL NOT be incremented
- **AND** the pipeline SHALL continue to the next gate
- **AND** test_result SHALL be set to `"warn-fail"`

#### Scenario: Effective max_retries from GateConfig
- **WHEN** GateConfig has `max_retries` set to a non-None value
- **THEN** the verifier SHALL use that value instead of the global `max_verify_retries` parameter for all blocking gates in this change

#### Scenario: Review model override from GateConfig
- **WHEN** GateConfig has `review_model` set to a non-None value
- **THEN** the review gate SHALL use that model instead of the global `review_model` parameter

### Requirement: VG-PIPELINE uncommitted work check
Ordered steps: **uncommitted-check →** build → test → e2e → scope check → test file check → review → rules → verify → merge queue. The uncommitted-check step runs before VG-BUILD and after the merge-rebase fast path early return.

#### Scenario: Uncommitted work blocks verify gate
- **WHEN** `handle_change_done()` is called for a change
- **AND** `git_has_uncommitted_work(wt_path)` returns `(True, summary)`
- **THEN** the verify gate SHALL fail with reason containing "uncommitted" and the summary
- **AND** the change SHALL be retried (re-dispatched) if retry budget allows

#### Scenario: Clean worktree proceeds to build gate
- **WHEN** `handle_change_done()` is called for a change
- **AND** `git_has_uncommitted_work(wt_path)` returns `(False, "")`
- **THEN** the verify gate SHALL proceed to the VG-BUILD step

#### Scenario: Merge-rebase fast path skips uncommitted check
- **WHEN** a change returns from a rebase cycle
- **THEN** the uncommitted-check step SHALL be skipped (rebase may leave expected state)

---

## MODIFIED Requirements

### Requirement: Verify gate results SHALL be preserved across monitor restart
When the monitor restarts (crash recovery or manual restart), it SHALL check for changes in "verifying" status that already have all blocking gates passed. Such changes SHALL proceed to merge instead of being re-dispatched. The check SHALL cover ALL blocking gates, not just a subset.

#### Scenario: Monitor dies after verify passes but before merge
- **WHEN** a change has status "verifying"
- **AND** all blocking verify gates have result "pass", "skipped", or "warn-fail" (test_result, build_result, review_result, scope_check, e2e_result, spec_coverage_result)
- **AND** the monitor restarts and polls active changes
- **THEN** the monitor SHALL proceed to merge the change
- **AND** the monitor SHALL NOT re-dispatch a retry agent

#### Scenario: Change in verifying with incomplete gates after restart
- **WHEN** a change has status "verifying"
- **AND** one or more blocking gates have no result (empty/null)
- **AND** the monitor restarts
- **THEN** the monitor SHALL re-run the verify gate from the beginning

#### Scenario: Change in verifying with failed rules gate after restart
- **WHEN** a change has status "verifying"
- **AND** test_result="pass", build_result="pass", review_result="pass", scope_check="pass"
- **AND** rules result is "fail" (stored in extras)
- **AND** the monitor restarts
- **THEN** the monitor SHALL NOT fast-merge the change
- **AND** SHALL re-run the verify gate

### Requirement: Completion detection SHALL respect merge queue
The `_check_completion` function SHALL NOT declare orchestration complete while the merge queue contains unmerged changes.

#### Scenario: All changes verified but merge queue non-empty
- **WHEN** all changes have status "done" (gates passed, queued for merge)
- **AND** `state.merge_queue` is non-empty
- **THEN** `_check_completion` SHALL return `False`
- **AND** the monitor loop SHALL continue running

#### Scenario: Merge exception leaves change in done status
- **WHEN** `merge_change()` throws an unhandled exception
- **AND** the change status remains "done" (not updated to "merged" or "merge-blocked")
- **AND** the change is still in `merge_queue`
- **THEN** `_check_completion` SHALL return `False`
- **AND** the next poll cycle SHALL retry the merge

#### Scenario: Empty merge queue with all changes resolved
- **WHEN** all changes have terminal status ("merged", "failed", "skipped", "merge-blocked")
- **AND** `state.merge_queue` is empty
- **THEN** `_check_completion` SHALL evaluate normally (may return `True`)

### Requirement: Crash recovery retry count SHALL not double-increment
The `_recover_verify_failed` function in the engine SHALL resume verify-failed changes without incrementing `verify_retry_count`, because `handle_change_done` already incremented it before setting the status to "verify-failed".

#### Scenario: Normal verify-failed recovery
- **WHEN** a change has status "verify-failed" after orchestrator restart
- **AND** `verify_retry_count` is already incremented by `handle_change_done`
- **THEN** `_recover_verify_failed` SHALL call `resume_change` without incrementing `verify_retry_count` again

#### Scenario: Recovery with exhausted retries
- **WHEN** a change has status "verify-failed"
- **AND** `verify_retry_count >= max_verify_retries`
- **THEN** `_recover_verify_failed` SHALL set status to "failed" without incrementing the counter

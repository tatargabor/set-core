<!-- NOTE: Existing gate-profiles scenarios (infrastructure skip, feature run-all, warn-mode test failure, effective max_retries, review model override) are preserved unchanged. This delta only adds the uncommitted-check step. -->

## MODIFIED Requirements

### Requirement: VG-PIPELINE — Gate pipeline (handle_change_done)
- Ordered steps: **uncommitted-check →** build → test → e2e → scope check → test file check → review → rules → verify → merge queue
- Each step with retry logic (verify_retry_count vs max_verify_retries)
- Retry token tracking: snapshot tokens before retry, compute diff on return
- Merge-rebase fast path: skip verify gate for returning rebase changes
- Gate timing: accumulate per-step ms, emit VERIFY_GATE event with totals
- Per-change skip flags: skip_test, skip_review honored
- Build step: detect package manager, run build:ci or build script, check main branch on failure
- Test file existence check: blocking for feature/infrastructure/foundational types
- Spec coverage step: non-blocking warning. `spec_coverage_result=fail` SHALL be recorded in state but SHALL NOT set `verify_ok = False` or trigger a retry. The VERIFY_GATE event SHALL include `spec_coverage` and `spec_coverage_blocking: false` fields.

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

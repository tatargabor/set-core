# Spec: Merger Gate Integrity

## Status: new

## Requirements

### REQ-NOOP-SKIP: No-op changes must not get "merged" status
- When `_is_no_op_change()` returns True (0 commits on branch beyond main), the change MUST be marked `"skipped"` (not "merged")
- The `merge_change()` function MUST NOT be called for no-op changes
- `gate_total_ms` MUST be set to 0 and `test_result` to `"skip_noop"` for traceability
- The monitor/sentinel should treat "skipped" as a terminal state (no retry, no redispatch)

### REQ-COVERAGE-GIT-VERIFY: Coverage must verify actual git state
- `reconcile_coverage()` MUST verify each "merged" change is actually in main before updating coverage
- Verification: `git merge-base --is-ancestor <change-branch-tip> <main>` returns 0
- If the change branch doesn't exist or is not an ancestor of main, do NOT mark coverage as "merged"
- Log a warning when state says "merged" but git says otherwise

### REQ-PREBUILD-BLOCKING: integration_pre_build must be a blocking gate
- If `profile.integration_pre_build(wt_path)` returns False, `_run_integration_gates()` MUST return False
- The current non-blocking warning at merger.py:778 MUST become a gate failure
- Exception handling: if `integration_pre_build()` throws, treat as gate failure (return False), not warning

### REQ-MERGE-VERIFY: Post-merge git verification
- After `merge_change()` sets status to "merged", verify that the change branch is actually an ancestor of main
- If `git merge-base --is-ancestor` fails, log an error and set status to `"merge-failed"` instead of "merged"
- Do NOT call `update_coverage_status()` with "merged" unless git verification passes

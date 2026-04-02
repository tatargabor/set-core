# Tasks: merger-gate-integrity

## 1. No-op changes → "skipped" status

- [x] 1.1 In `merger.py` `execute_merge_queue()` (~line 1033-1036): when `_is_no_op_change()` returns True, set status to `"skipped"` via `update_change_field()`, set `gate_total_ms: 0`, `test_result: "skip_noop"`, then `continue` — do NOT proceed to `merge_change()` [REQ: REQ-NOOP-SKIP]
- [x] 1.2 In `engine.py`: ensure the monitor treats `"skipped"` as a terminal status (like "merged") — the `_check_all_done()` or equivalent must count skipped changes as complete [REQ: REQ-NOOP-SKIP]

## 2. integration_pre_build blocking

- [x] 2.1 In `merger.py` `_run_integration_gates()` (~line 777-780): change `integration_pre_build` from non-blocking warning to blocking gate failure. If returns False → `return False`. If throws → log error and `return False` [REQ: REQ-PREBUILD-BLOCKING]

## 3. Coverage git verification

- [x] 3.1 In `digest.py` `reconcile_coverage()` (~line 864-870): before marking a requirement as "merged", verify with `git merge-base --is-ancestor <branch-tip> <main>`. Add helper `_is_branch_merged(change_name: str) -> bool` that runs the git check [REQ: REQ-COVERAGE-GIT-VERIFY]
- [x] 3.2 In the reconcile loop: if state says "merged" but git says not merged, log warning and skip the coverage update for that change [REQ: REQ-COVERAGE-GIT-VERIFY]

## 4. Post-merge git verification

- [x] 4.1 In `merger.py` `merge_change()` (~line 493): after setting status to "merged", run `git merge-base --is-ancestor change/<name> <main>`. If it fails, rollback status to `"merge-failed"` and log error [REQ: REQ-MERGE-VERIFY]
- [x] 4.2 Only call `update_coverage_status(change_name, "merged")` if the git verification passes [REQ: REQ-MERGE-VERIFY]

## Acceptance Criteria

- [x] AC-1: WHEN a change has 0 commits on its branch THEN status is "skipped" (not "merged") and gate_total_ms is 0 [REQ: REQ-NOOP-SKIP]
- [x] AC-2: WHEN integration_pre_build returns False THEN the gate pipeline fails and the change is merge-blocked [REQ: REQ-PREBUILD-BLOCKING]
- [x] AC-3: WHEN state says "merged" but branch is not an ancestor of main THEN coverage-merged.json does NOT include that change's requirements [REQ: REQ-COVERAGE-GIT-VERIFY]
- [x] AC-4: WHEN merge_change runs set-merge but the branch is still not in main THEN status is "merge-failed" not "merged" [REQ: REQ-MERGE-VERIFY]

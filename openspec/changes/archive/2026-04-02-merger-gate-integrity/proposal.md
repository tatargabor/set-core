# Proposal: merger-gate-integrity

## Why

Production orchestration runs reveal 4 interconnected bugs where changes get "merged" status without actual gate validation or git merge. This causes false 100% coverage, missing code on main, and silent sentinel completion with incomplete work.

Root cause: the merger pipeline conflates "no commits on branch" with "already merged" and skips gates entirely. The coverage tracker reads from state.json (which has false "merged" entries) instead of verifying against actual git state.

## What Changes

### Fix 1: No-op changes must not get "merged" status
- `merger.py` `execute_merge_queue()`: when `_is_no_op_change()` returns True, mark the change as `"skipped"` instead of proceeding to `merge_change()`. A no-op branch with 0 commits is NOT "merged" — it was never implemented.

### Fix 2: Coverage reconciliation must verify git state
- `digest.py` `reconcile_coverage()`: before marking a requirement "merged", verify with `git merge-base --is-ancestor change/<name> main` that the branch is actually in main's history. If not, don't update coverage.

### Fix 3: integration_pre_build must be blocking
- `merger.py` `_run_integration_gates()`: if `profile.integration_pre_build()` returns False, fail the gate pipeline (return False). Currently it's a non-blocking warning, causing downstream build/test failures with cryptic errors.

### Fix 4: Post-merge coverage validation
- After setting status to "merged" in `merge_change()`, verify that `git diff main..change/<name>` is empty (the branch is actually merged). If diff exists, log an error and don't update coverage.

## Capabilities

### Modified Capabilities
- `merger-no-op-detection`: No-op changes get "skipped" status, not "merged"
- `coverage-reconciliation`: Git-verified coverage updates
- `integration-pre-build`: Blocking gate, not non-blocking warning
- `merge-verification`: Post-merge git state validation

## Impact
- **Modified files**: `lib/set_orch/merger.py`, `lib/set_orch/digest.py`
- **Risk**: Medium — changes merge pipeline behavior. Well-scoped to specific code paths.
- **Dependencies**: None

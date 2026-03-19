## 1. Sentinel: checkpoint-aware stuck detection

- [x] 1.1 In `bin/set-sentinel` `check_orchestrator_liveness()`, read state file status and return 0 (not stuck) when `status == "checkpoint"`. On `jq` parse failure use `|| return 0` (fail safe — skip the kill, not proceed with it).
- [x] 1.2 Add `CHECKPOINT_MAX_WAIT` variable (default: 86400 / 24h). Read `checkpoint_started_at` from state file. If checkpoint age exceeds max wait, return 1 (stuck) so sentinel stops with a clear log message.
- [x] 1.3 Verify existing `fix_stale_state()` checkpoint handling (line 361-362) is still correct — confirm it preserves checkpoint status and that running→stalled marking for dead-PID changes doesn't break checkpoint resume.

## 2. Coverage reconciliation

- [x] 2.1 Add `reconcile_coverage(state_file, digest_dir)` function to `lib/set_orch/digest.py`: read coverage.json using `cov_data.get("coverage", {})` pattern, compare each requirement's change status against state file, update any non-merged (`!= "merged"`) entries to "merged" where the owning change is merged in state, write to coverage-merged.json via read-merge-write (same pattern as `update_coverage_status()`), return count of fixed requirements. Return 0 with no error if coverage.json doesn't exist.
- [x] 2.2 Call `reconcile_coverage()` from `_check_completion()` in `lib/set_orch/engine.py` — insert after the early-return guard (after line ~607, the "not all resolved" check) but before any terminal branch (dep_blocked, total_failure, done/replan). Wrap in try/except, log WARNING with count if any requirements were fixed.

## 3. Verification

- [x] 3.1 Manual test: create a mock state with merged changes but planned coverage, run `reconcile_coverage()` and verify coverage.json is fixed and coverage-merged.json is updated via read-merge-write
- [x] 3.2 Verify sentinel liveness check returns 0 when state is checkpoint and age < max wait, returns 1 when age > max wait
- [x] 3.3 Verify that when state file has status=checkpoint and orchestrator PID is dead: fix_stale_state() preserves checkpoint status, running changes are marked stalled, and restarted orchestrator resumes from checkpoint

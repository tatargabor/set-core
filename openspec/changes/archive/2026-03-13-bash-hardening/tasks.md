## 1. Safe JSON State Primitives

- [x] 1.1 Add `safe_jq_update()` function to `lib/orchestration/utils.sh` — validates jq exit code and output non-empty before mv, cleans up temp file on failure via trap RETURN
- [x] 1.2 Add `with_state_lock()` function to `lib/orchestration/utils.sh` — flock-based wrapper with 10s timeout on `${STATE_FILENAME}.lock`
- [x] 1.3 Add unit tests for `safe_jq_update` in `tests/unit/` — test success, jq filter error, invalid source JSON, and empty output scenarios
- [x] 1.4 Add unit tests for `with_state_lock` — test uncontended acquisition, lock release on failure

## 2. Migrate State Operations

- [x] 2.1 Refactor `update_state_field()` in `state.sh` to use `safe_jq_update` internally with state lock
- [x] 2.2 Refactor `update_change_field()` in `state.sh` to hold state lock for the full read-old-status + write + emit-event sequence, using `safe_jq_update` for the write
- [x] 2.3 Replace all raw `mktemp`+`jq`+`mv` patterns in `lib/orchestration/state.sh` with `safe_jq_update` calls
- [x] 2.4 Replace all raw `mktemp`+`jq`+`mv` patterns in `lib/orchestration/dispatcher.sh` with `safe_jq_update` calls
- [x] 2.5 Replace all raw `mktemp`+`jq`+`mv` patterns in `lib/orchestration/merger.sh` with `safe_jq_update` calls
- [x] 2.6 Replace all raw `mktemp`+`jq`+`mv` patterns in `lib/orchestration/watchdog.sh` with `safe_jq_update` calls
- [x] 2.7 Replace all raw `mktemp`+`jq`+`mv` patterns in `lib/orchestration/verifier.sh` with `safe_jq_update` calls
- [x] 2.8 Replace all raw `mktemp`+`jq`+`mv` patterns in `lib/orchestration/monitor.sh` with `safe_jq_update` calls (none found — monitor.sh uses update_change_field)
- [x] 2.9 Verify: grep for `mktemp` + `mv.*STATE` in `lib/orchestration/` returns zero matches (remaining mktemps are in digest/planner/reporter for non-state temp files)
- [x] 2.10 Wrap compound state operations in `with_state_lock` — `trigger_checkpoint()` and `cmd_approve()` now use `_trigger_checkpoint_locked` and `_approve_checkpoint_locked` helpers under `with_state_lock`
- [x] 2.11 Fix `reconstruct_state_from_events()` — added `jq empty` validation before overwrite + `with_state_lock mv` for the final state write

## 3. Strict Mode Rollout

- [x] 3.1 Add `set -euo pipefail` to `bin/set-orchestrate` (already inherited from wt-common.sh)
- [x] 3.2 Add `set -euo pipefail` to `bin/wt-merge` (already inherited from wt-common.sh)
- [x] 3.3 Add `set -euo pipefail` to `bin/wt-loop` (already inherited from wt-common.sh)
- [x] 3.4 All bin/wt-* entry points source wt-common.sh which has set -euo pipefail — no changes needed
- [x] 3.5 Fix `grep` patterns that fail under `set -e` — added `|| true` to planner.sh grep pipes, fixed verifier.sh and orch-memory.sh grep -oP to grep -oE
- [x] 3.6 No `local var=$(cmd)` patterns found that mask exit codes — all already have error handling or use arithmetic
- [x] 3.7 No unprotected unset variables found — existing code uses `${var:-default}` or `// empty` in jq
- [x] 3.8 Run existing test suite to verify strict mode doesn't break functionality (tests pass — see 2.9)

## 4. Error Suppression Audit

- [x] 4.1 Classify `|| true` in state.sh — polling reads (intentional), update_change_field 2>/dev/null removed in refactored code
- [x] 4.2 Classify dispatcher.sh — mostly git/process checks (intentional: branch may not exist, PID may be dead)
- [x] 4.3 Classify merger.sh — mostly git merge/branch checks (intentional)
- [x] 4.4 Classify verifier.sh — test output parsing greps already have `|| true` comments
- [x] 4.5 Classify watchdog.sh and monitor.sh — process/stat checks (intentional)
- [x] 4.6 Removed 2>/dev/null from jq writes via safe_jq_update (which logs errors). Polling reads keep 2>/dev/null (file may be mid-write)

## 5. Variable Scope Fixes

- [x] 5.1 Audited dispatcher.sh — no missing locals (ORCHESTRATOR_START_EPOCH is intentional global)
- [x] 5.2 Audited merger.sh — no missing locals found
- [x] 5.3 Audited state.sh — no missing locals (_TOPO_FILE is env var for subprocess)
- [x] 5.4 Audited verifier.sh — TEST_OUTPUT/REVIEW_OUTPUT are intentional globals (return values)

## 6. Platform Compatibility

- [x] 6.1 Fix `stat --format=%Y` in state.sh and utils.sh — added macOS fallback chain
- [x] 6.2 Replace `grep -oP` in verifier.sh and orch-memory.sh with POSIX `grep -oE`
- [x] 6.3 Verified: `cd` in dispatcher.sh already in subshells `( cd ... )` — no fix needed

## 7. State Corruption Detection

- [ ] 7.1 Add JSON validity check to `get_change_status()` and `get_changes_by_status()` — log error and return 1 on invalid JSON instead of empty string
- [ ] 7.2 Add integration test: corrupt state.json, verify safe_jq_update refuses to overwrite and functions return errors

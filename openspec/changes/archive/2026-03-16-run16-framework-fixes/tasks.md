## 1. Build-fix retry separation (Bug #37)

- [x] 1.1 In `lib/set_orch/verifier.py`, remove the `verify_retry_count += 1` and `update_change_field(..., "verify_retry_count", ...)` calls from the build-failure retry path (around line 1306-1308). Keep the `status = "verify-failed"` and `resume_change()` dispatch — just don't increment the counter.
- [x] 1.2 Verify that test-failure, review-failure, scope-failure, and spec-verify-failure paths still increment `verify_retry_count` normally (no changes to those paths).
- [x] 1.3 Add a comment at the build-fix retry site explaining why `verify_retry_count` is not incremented: build self-healing is bounded by Ralph's iteration limit, not the verify budget.

## 2. Generated file conflict auto-resolve (Bug #38)

- [x] 2.1 In `lib/set_orch/dispatcher.py`, add `_AUTO_RESOLVE_PREFIXES` set containing `".claude/"` alongside the existing `_CORE_GENERATED_FILE_PATTERNS`.
- [x] 2.2 Extract the generated-file check at line 155-160 into a helper function `_is_generated_file(path: str) -> bool` that returns True if `os.path.basename(path)` is in `_CORE_GENERATED_FILE_PATTERNS` OR if `path.startswith(prefix)` for any prefix in `_AUTO_RESOLVE_PREFIXES`.
- [x] 2.3 Replace the inline `basename not in _get_generated_file_patterns()` check with a call to `_is_generated_file()`.
- [x] 2.4 Verify the same pattern is also used in `merger.py` merge conflict handling — if `_handle_merge_conflict` has similar basename-only checks, update those too.

## 3. Stale flock recovery (Bug #41)

- [x] 3.1 In `bin/set-sentinel`, after the `flock -n 9` failure block (line 73-76), add PID validation: read PID from `sentinel.pid`, check `kill -0 "$existing_pid" 2>/dev/null`, if dead then `rm -f "$LOCK_FILE"`, re-open fd 9, retry flock.
- [x] 3.2 Handle edge case: `sentinel.pid` missing or empty — treat as stale (remove lock, retry).
- [x] 3.3 Log the recovery: "Recovered stale lock from dead PID $pid" or "Recovered stale lock (no PID file)".

## 4. Verify gate preservation across monitor restart (Bug #5b)

- [x] 4.1 In `lib/set_orch/engine.py` `_poll_active_changes()`, add a check before calling `poll_change()`: if `change.status == "verifying"` and the change has stored gate results where all blocking gates are "pass" or "skipped", call the merge path directly instead of polling.
- [x] 4.2 Read the gate results from `change.extras` (keys: `test_result`, `build_result`, `review_result`, `scope_result`) and compare against the gate config to determine which gates are blocking.
- [x] 4.3 Add a staleness guard: only trigger the fast-merge path if the change has been in "verifying" for >30 seconds (use `change.extras.get("verify_started_at")` or similar timestamp).

## 5. Testing

- [x] 5.1 Test Bug #37 fix: manually set a change to verify-failed via build failure, verify that `verify_retry_count` stays at 0 after the build-fix retry dispatch.
- [x] 5.2 Test Bug #38 fix: create a merge conflict on `.claude/activity.json` and `.claude/logs/test.log`, verify both are auto-resolved.
- [x] 5.3 Test Bug #41 fix: write a stale PID to `sentinel.pid`, create `sentinel.lock`, verify sentinel starts successfully with recovery log message.
- [x] 5.4 Test Bug #5b fix: set a change to "verifying" with all gates passed in state, start monitor, verify it proceeds to merge.

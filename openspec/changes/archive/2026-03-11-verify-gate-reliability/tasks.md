### 1. Verify gate: build-first order

- [x] 1.1 Reorder `verify_and_merge_change()` in `lib/orchestration/verifier.sh`: move the build verification block (currently Step 2, ~line 969) BEFORE the test execution block (currently Step 1, ~line 872). Update step comments accordingly (Step 1: Build, Step 2: Test, Step 3: E2E).
- [x] 1.2 Update the fail-fast logic: build failure should skip test, E2E, review, and verify. Test failure should skip E2E, review, and verify (same as before but now test is Step 2).
- [x] 1.3 Update the retry dispatch: when build fails, the retry context message should indicate build failure (already works, just verify the retry path handles the new ordering).
- [x] 1.4 Update the gate timing log line to reflect new order: `build=${gate_build_ms}ms, test=${gate_test_ms}ms` (swap order in log message for clarity).

### 2. wt-merge: JSON file auto-resolve

- [x] 2.1 Add `auto_resolve_json_files()` function to `bin/wt-merge` (after `auto_resolve_package_json`). Logic: iterate conflicted files, for each `.json` file (excluding `package.json`): extract ours/theirs via `git show :2:/$file` and `:3:/$file`, validate with `jq empty`, deep-merge with the same jq strategy as `auto_resolve_package_json`, write result, `git add`. Return 0 if at least one file resolved.
- [x] 2.2 Hook `auto_resolve_json_files()` into the merge flow at ~line 547 (after `auto_resolve_package_json` block, before `llm_resolve_conflicts`). Follow the same pattern: call it, re-check conflicts, commit if all resolved.

### 3. Watchdog: log level change

- [x] 3.1 In `lib/orchestration/watchdog.sh` line 123: change `log_warn` to `log_debug` for the "hash loop but PID alive" message. Keep `emit_event "WATCHDOG_WARN"` unchanged on line 124-125.

### 4. Spec updates

- [x] 4.1 Update `openspec/specs/verify-gate/spec.md`: change the step order in "Full gate pipeline" scenario from test→build→e2e to build→test→e2e. Update the fail-fast scenarios accordingly.
- [x] 4.2 Update `openspec/specs/orchestration-watchdog/spec.md`: add note that PID-alive hash loop logging is DEBUG level, not WARN.
- [x] 4.3 Add `openspec/specs/json-translation-merge/spec.md` from the change specs (copy to main specs after merge).

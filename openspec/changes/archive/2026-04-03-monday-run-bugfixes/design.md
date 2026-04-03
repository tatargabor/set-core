## Context

4 bugs found across production orchestration runs. All are in the merge/gate pipeline (`merger.py`, `engine.py`). The fixes are surgical — no architectural changes needed.

## Decisions

### D1: No-test-files detection — output string matching

Check the test gate output for known "no tests found" patterns:
- vitest: `"No test files found"`, `"no tests found"`
- jest: `"No tests found"`, `"testMatch:"` without matches

Parse in `_run_integration_gates()` after the test command returns non-zero. If matched → return `GateResult(status="skip")` instead of `fail`.

**Why not a separate pre-check?** The test command itself already tells us. Parsing its output is simpler than running a separate `find` for test files.

### D2: Same-output retry detection — hash comparison

After each gate retry, hash the output. Store last 3 hashes. If all 3 are identical → stop retrying, mark as `fail` with `reason="identical_output"`.

Use a simple SHA256 of the first 2000 chars of output (avoids timestamp-only differences at the end).

### D3: TypeError fix — int() coercion

Replace `extras.get("total_merge_attempts", 0)` with `int(extras.get("total_merge_attempts") or 0)` at all 4 usage sites. This handles both missing key (default 0) and explicit None.

### D4: Pre-merge dep validation — check in execute_merge_queue

Before running integration gates for a change, check `change.depends_on` against the state. If any dep is not `merged`/`done`/`skip_merged` → remove from queue, set `dep-blocked`.

In `_poll_active_changes()`, add a check: if status is `dep-blocked` and all deps are now merged → set back to `done`.

### D5: Merge-blocked auto-recovery — poll loop check

In the engine's poll cycle, scan `merge-blocked` changes. For each, check if blocking issues are resolved (query issue registry). If no active blockers → set to `done`, re-queue.

## Risks

- **[Risk] False positive on "no tests"** → Only match exact known strings, not substrings. Mitigated by requiring both the string match AND non-zero exit code.
- **[Risk] Hash collision on different failures** → SHA256 collision is astronomically unlikely. The 2000-char prefix avoids timestamp noise.

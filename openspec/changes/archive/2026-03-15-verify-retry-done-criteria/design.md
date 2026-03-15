## Context

The retry loop (`resume_change()` → `wt-loop start --done test`) is broken because `is_done("test")` has no implementation — it falls through to `return False`. The agent applies the fix correctly but the loop never exits. After `max_iter` iterations, the change fails.

The fix is straightforward: implement `_check_test_done()` and wire it into `is_done()`. The test command must flow from the orchestrator (which knows the configured test command) to the loop.

## Goals / Non-Goals

**Goals:**
- `is_done("test")` runs the test command and returns True on pass
- Test command flows from orchestrator → wt-loop → loop-state.json → `_check_test_done()`
- Fallback: if no test command provided, auto-detect via `config.auto_detect_test_command()`
- If no test command found at all, fall back to build check (`_check_build_done()`)

**Non-Goals:**
- New directives for retry limits — the current `max_iter=5` for review retries is adequate
- Changing the retry trigger logic in verifier.py — that works correctly
- Changing what constitutes a review failure — out of scope

## Decisions

### D1: Pass test command via `--test-command` flag on wt-loop

**Decision**: Add `--test-command <cmd>` to `wt-loop start`. Store in `loop-state.json`. `_check_test_done()` reads from state, falls back to `config.auto_detect_test_command(wt_path)`.

**Rationale**: The orchestrator already knows the test command (from `directives.test_command` or `config.auto_detect_test_command()`). Passing it explicitly avoids the loop re-reading orchestration config, keeping loop decoupled from orchestrator internals.

**Alternative rejected**: Have `_check_test_done()` auto-detect only (no explicit passing). Problem: in the worktree, `wt/orchestration/config.yaml` may have `test_command: pnpm test` which is the authoritative source, but `auto_detect_test_command()` only checks profile + package.json, not the orchestration config. Explicit passing ensures the orchestrator's resolved command is used.

### D2: Fallback chain in `_check_test_done()`

```
1. loop-state.json → test_command field (passed via --test-command)
2. config.auto_detect_test_command(wt_path) (profile → legacy)
3. _check_build_done(wt_path) (last resort — at least verify it builds)
```

**Rationale**: Defense in depth. If the orchestrator didn't pass a test command (e.g., old loop-state format), auto-detect still works. If auto-detect fails (no package.json), build check is better than `return False` (which is the current broken behavior).

### D3: Test command resolution in `resume_change()`

**Decision**: `resume_change()` reads the test command from:
1. `directives.test_command` in orchestration state extras
2. `config.auto_detect_test_command(wt_path)` as fallback

Then passes it to `wt-loop start --test-command <cmd>`.

**Rationale**: The orchestrator state already has `test_command` from directive parsing. Using the same resolution the verifier uses ensures consistency.

### D4: Run test command directly, not via PM

**Decision**: `_check_test_done()` runs the test command as a shell string (`subprocess.run(cmd, shell=True)`), not decomposed into PM + script name.

**Rationale**: Test commands can be complex (`pnpm test`, `pytest -x`, `make test`). The orchestrator already resolves the full command. Running it as-is is more reliable than trying to parse PM from the command string. This matches how the verifier runs test commands.

## Risks / Trade-offs

- **[Risk] Long test runs blocking loop exit detection**: Tests may take 30-60s → Mitigation: 300s timeout on subprocess (same as `_check_build_done`)
- **[Risk] Test command not available in worktree**: If worktree was created before deps installed → Mitigation: fallback chain (D2) catches this — build check or True-on-no-command
- **[Risk] Flaky tests causing loop to never exit**: If tests fail intermittently → Mitigation: This is a pre-existing problem — the loop has max_iter=5 as a hard cap. The agent gets 5 tries then fails. Flaky test handling is out of scope.

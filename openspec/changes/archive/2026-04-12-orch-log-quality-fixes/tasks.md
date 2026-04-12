# Tasks: orch-log-quality-fixes

## 1. Spec verify sentinel handling

- [x] 1.1 Update `lib/set_orch/verifier.py` `run_spec_verify_gate` (around line 2438): change "timeout" log message to "missing VERIFY_RESULT sentinel — assuming PASS (verify skill prompt issue)" and tag with `[ANOMALY]` [REQ: spec-verify-gate-detects-missing-sentinel]
- [x] 1.2 Update `templates/openspec/skills/openspec-verify-change/SKILL.md` (or wherever the verify skill source is) to add explicit instruction: agent MUST output `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` as the final line [REQ: verify-skill-prompt-requires-sentinel]
- [x] 1.3 Verify the deployment template — check `templates/core/` and `.claude/skills/openspec-verify-change/SKILL.md` for the actual skill source [REQ: verify-skill-prompt-requires-sentinel]

## 2. Context window metric correction

- [x] 2.1 Update `_context_window_for_model` in `lib/set_orch/verifier.py` (around line 66) to default to 1M for opus/sonnet/claude-4.x families. Keep `[1m]` and add `[200k]` explicit suffix support [REQ: context-window-metric-uses-correct-window-size]
- [x] 2.2 Update `_capture_context_tokens_end` in `lib/set_orch/verifier.py` (around line 1756) to compute peak from `iterations` list (max of `cache_create_tokens`), not `total_cache_create` [REQ: context-tokens-end-uses-peak-iteration-value]
- [x] 2.3 Verify the loop-state.json structure has `iterations` array with `cache_create_tokens` per entry [REQ: context-tokens-end-uses-peak-iteration-value]

## 3. run_git best_effort flag

- [x] 3.1 Add `best_effort: bool = False` parameter to `run_git` in `lib/set_orch/subprocess_utils.py` (around line 380). Skip the WARNING log when `best_effort=True` and exit_code != 0 [REQ: run-git-supports-best-effort-mode]
- [x] 3.2 Update `lib/set_orch/merger.py` line ~735 to pass `best_effort=True` (note: it currently uses `run_command`, may need to switch to `run_git` first or add the flag to `run_command` as well — TBD during apply) [REQ: best-effort-flag-adopted-by-fetch-callers]
- [x] 3.3 Update `lib/set_orch/merger.py` line ~2229 same way [REQ: best-effort-flag-adopted-by-fetch-callers]
- [x] 3.4 Update `lib/set_orch/verifier.py` line ~2474 to pass `best_effort=True` [REQ: best-effort-flag-adopted-by-fetch-callers]
- [x] 3.5 Update `lib/set_orch/loop_tasks.py` line ~344 to pass `best_effort=True` (uses subprocess.run directly — may need to switch to run_git) [REQ: best-effort-flag-adopted-by-fetch-callers]

## 4. Design context anomaly conditional

- [x] 4.1 Update `dispatch_change` in `lib/set_orch/dispatcher.py` (around line 1790) to check for design asset files before logging ANOMALY [REQ: design-context-anomaly-is-conditional]

## 5. Test plan log level

- [x] 5.1 Change `parse_test_plan` in `lib/set_orch/test_coverage.py` line 227: `logger.warning` → `logger.debug` [REQ: test-plan-missing-logs-at-debug-level]

## 6. Worktree-aware claude project dir

- [x] 6.1 Update `get_current_tokens` in `lib/loop/state.sh` (around line 204) to detect worktrees via `git rev-parse --git-common-dir` and derive parent repo dir for slug computation [REQ: worktree-aware-claude-project-dir]
- [x] 6.2 Test the derivation manually with a worktree path before committing [REQ: worktree-aware-claude-project-dir]

## 7. Verification

- [x] 7.1 Run the python unit tests for verifier (if any) to ensure no regression [REQ: context-window-metric-uses-correct-window-size]
- [x] 7.2 Manually verify the changes don't break a fresh E2E run (no need for full minishop run, just dispatch one change and check logs) [REQ: spec-verify-gate-detects-missing-sentinel]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN agent writes PASS sentinel THEN gate returns pass with correct log [REQ: spec-verify-gate-detects-missing-sentinel, scenario: agent-writes-pass-sentinel]
- [x] AC-2: WHEN agent writes FAIL sentinel THEN gate returns fail with retry context [REQ: spec-verify-gate-detects-missing-sentinel, scenario: agent-writes-fail-sentinel]
- [x] AC-3: WHEN agent writes neither THEN gate logs missing-sentinel WARNING and returns pass [REQ: spec-verify-gate-detects-missing-sentinel, scenario: agent-writes-neither-sentinel]
- [x] AC-4: WHEN verify skill markdown is read THEN it contains the sentinel requirement instruction [REQ: verify-skill-prompt-requires-sentinel, scenario: verify-skill-includes-sentinel-requirement]
- [x] AC-5: WHEN _context_window_for_model("opus") is called THEN returns 1_000_000 [REQ: context-window-metric-uses-correct-window-size, scenario: default-opus-model]
- [x] AC-6: WHEN _context_window_for_model("sonnet") is called THEN returns 1_000_000 [REQ: context-window-metric-uses-correct-window-size, scenario: default-sonnet-model]
- [x] AC-7: WHEN _context_window_for_model("opus[1m]") is called THEN returns 1_000_000 [REQ: context-window-metric-uses-correct-window-size, scenario: explicit-1m-suffix]
- [x] AC-8: WHEN _context_window_for_model("opus[200k]") is called THEN returns 200_000 [REQ: context-window-metric-uses-correct-window-size, scenario: explicit-200k-requested]
- [x] AC-9: WHEN loop_state has 1 iteration with cache_create_tokens=300000 THEN context_tokens_end=300000 [REQ: context-tokens-end-uses-peak-iteration-value, scenario: single-iteration]
- [x] AC-10: WHEN loop_state has 3 iterations with values [300000,350000,280000] THEN context_tokens_end=350000 [REQ: context-tokens-end-uses-peak-iteration-value, scenario: multiple-iterations]
- [x] AC-11: WHEN run_git("status") fails THEN WARNING is logged [REQ: run-git-supports-best-effort-mode, scenario: default-behavior-unchanged]
- [x] AC-12: WHEN run_git("fetch","origin","main",best_effort=True) fails THEN no WARNING [REQ: run-git-supports-best-effort-mode, scenario: best-effort-fetch-fails]
- [x] AC-13: WHEN _integrate_main_into_branch runs without origin THEN no fetch warning [REQ: best-effort-flag-adopted-by-fetch-callers, scenario: merger-fetch]
- [x] AC-14: WHEN dispatching in project without design files and context is empty THEN INFO log not ANOMALY [REQ: design-context-anomaly-is-conditional, scenario: no-design-assets]
- [x] AC-15: WHEN design-snapshot.md exists but context is empty THEN ANOMALY warning [REQ: design-context-anomaly-is-conditional, scenario: design-assets-exist-but-context-is-empty]
- [x] AC-16: WHEN parse_test_plan(nonexistent path) is called THEN debug log not warning [REQ: test-plan-missing-logs-at-debug-level, scenario: journey-test-plan-missing]
- [x] AC-17: WHEN get_current_tokens runs in worktree THEN derives parent repo, no warning [REQ: worktree-aware-claude-project-dir, scenario: running-in-a-worktree]
- [x] AC-18: WHEN get_current_tokens runs in regular repo THEN behavior unchanged [REQ: worktree-aware-claude-project-dir, scenario: running-in-a-regular-repo]

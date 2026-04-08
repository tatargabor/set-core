# Proposal: orch-log-quality-fixes

## Why

Log review of minishop-run2 surfaced 7 issues. Two are silent quality regressions disguised as cosmetic warnings:

1. **`spec_verify` gate is effectively a no-op** — 9/9 changes received PASS without verification because the agent never wrote the `VERIFY_RESULT:` sentinel. The "Spec verify timed out — non-blocking" message hides this.
2. **`context_tokens_end` metric reports 900% of window** — false alarm caused by two bugs: (a) `total_cache_create` is cumulative across iterations, not peak, and (b) `_context_window_for_model` returns 200K for `opus`/`sonnet` even though Claude 4.6 defaults to 1M context.

The remaining 5 issues are cosmetic warning spam (git fetch, design context anomaly, journey test plan, claude project dir, ANOMALY tag).

The planner-coverage gap (REQ-DATA-001/REQ-NAV-002 left uncovered) is **deliberately excluded** — it's a planner logic bug, not a logging issue, and warrants its own change.

## What Changes

- **Spec verify sentinel enforcement** — `/opsx:verify` skill explicitly requires `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` as the final line. Verifier still treats missing sentinel as PASS for backward compat, but logs at WARNING and emits an ANOMALY for sentinel tracking.
- **Context window metric correctness** — `_context_window_for_model` defaults to 1M for `opus`/`sonnet` (Claude 4.x baseline). `_capture_context_tokens_end` uses `max(iter.cache_create_tokens)` instead of `total_cache_create`.
- **Git fetch best-effort flag** — `run_git()` accepts `best_effort=True` parameter. Callers in `merger.py`, `verifier.py`, `loop_tasks.py` use it for `fetch origin`. No more spam.
- **Design context anomaly is conditional** — `[ANOMALY]` only when design assets exist but produce empty context. Otherwise INFO.
- **Test plan parsing log level** — `parse_test_plan` uses `logger.debug` when file is missing (callers always have a fallback).
- **Claude project dir warning silenced** — `lib/loop/state.sh` uses `git common-dir` to derive parent repo path for worktrees, eliminating the warn entirely (token usage stays per-repo, which matches current unfiltered fallback behavior).

## Capabilities

### Modified Capabilities
- `dispatch-core` — design context anomaly logic refinement
- `gate-runner` — spec_verify sentinel handling, retry on missing sentinel
- `subprocess-utils` — `run_git` best_effort flag
- `verifier` — context window metric fix
- `test-coverage` — log level fix
- `loop-state` — claude project dir derivation for worktrees

## Impact

- `lib/set_orch/dispatcher.py` — design context anomaly conditional
- `lib/set_orch/verifier.py` — context window fix, spec_verify sentinel logging
- `lib/set_orch/subprocess_utils.py` — `run_git` best_effort flag
- `lib/set_orch/merger.py` — use `best_effort=True` for fetch calls
- `lib/set_orch/loop_tasks.py` — use `best_effort=True` for fetch calls
- `lib/set_orch/test_coverage.py` — log level fix
- `lib/loop/state.sh` — git common-dir derivation
- `templates/core/skills/openspec-verify-change/SKILL.md` — explicit sentinel requirement (or wherever the verify skill lives)

No test failures expected — all changes are log level / metric correction. The spec_verify sentinel change is additive (still PASSes on missing sentinel for compat).

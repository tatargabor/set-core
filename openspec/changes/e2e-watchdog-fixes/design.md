## Context

E2E #2 minishop test run (2026-03-08) completed successfully (4/4 changes merged, 49 tests pass, ~50 min) but exposed:
1. **Watchdog false-positive kills** (4x) during artifact creation phase — loop-state.json doesn't exist yet, watchdog hash detection escalates L1→L3 in ~30s
2. **Token tracking broken** — `wt-usage` crashes with `ModuleNotFoundError: No module named 'gui'`, `get_current_tokens()` always returns 0 via fallback
3. **`wt-sentinel` missing from install.sh** — already fixed in proposal
4. **Checkpoint blocks unattended E2E** — `merge_policy: checkpoint` requires manual `wt-orchestrate approve`

## Goals / Non-Goals

**Goals:**
- Eliminate watchdog false-positive kills during artifact creation phase
- Fix token tracking so orchestrator has real usage data
- Make E2E runnable unattended (no manual approval needed)

**Non-Goals:**
- Rewrite watchdog escalation chain (current L1→L2→L3→L4 is fine when it triggers correctly)
- Add new watchdog detection modes beyond what exists
- Redesign wt-usage (just fix the import path issue)

## Decisions

### D1: Watchdog grace period for dispatched changes

**Problem:** After dispatch, Ralph needs 1-2 minutes for artifact creation (proposal, design, specs, tasks) before the loop starts and creates loop-state.json. The watchdog sees no loop-state.json, hashes are identical ("0:0:unknown"), and escalates.

**Decision:** In `watchdog_check()`, skip hash-based loop detection when:
- Status is `running` AND
- `loop-state.json` does not exist yet

The existing timeout check (WATCHDOG_TIMEOUT_RUNNING=600s) with PID-alive guard already handles the case where Ralph is truly dead. No new grace period timer needed.

**Alternative considered:** Adding a `dispatch_epoch` field and checking age < 120s. Rejected because the simpler "no loop-state = skip hash detection" captures the exact condition.

### D2: Fix wt-usage import path

**Problem:** `wt-usage` does `from gui.usage_calculator import UsageCalculator` but the `gui` package is not on Python path when called from arbitrary directories.

**Decision:** Fix the Python import in `wt-usage` to use the correct path relative to the wt-tools install. Add `sys.path.insert` pointing to the wt-tools lib directory, or use relative imports.

**Fallback:** If wt-usage fix is complex, add a lightweight bash-based token estimator in `get_current_tokens()` that reads JSONL session files directly and sums `usage.output_tokens` fields.

### D3: Auto-approve checkpoint for E2E

**Problem:** `merge_policy: checkpoint` pauses orchestration and waits for `wt-orchestrate approve`.

**Decision:** Add `checkpoint_auto_approve: true` directive. When set, checkpoint emits the event but immediately continues without waiting. The E2E run.sh config sets this.

**Alternative considered:** Changing E2E config to `merge_policy: eager`. Rejected because we want to test the checkpoint mechanism itself — just not block on it.

## Risks / Trade-offs

- **[Watchdog grace too permissive]** → Mitigated by only skipping hash detection, not timeout detection. If Ralph process dies during artifact creation, the 600s timeout + PID check still catches it.
- **[Token tracking still 0 after fix]** → wt-usage depends on Claude session JSONL files which may not exist in worktree contexts. The bash fallback estimator provides a safety net.
- **[checkpoint_auto_approve hides issues]** → Only used in E2E config, not default. Production orchestration still blocks.

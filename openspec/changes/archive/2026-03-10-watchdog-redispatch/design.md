## Context

The orchestrator watchdog (`lib/orchestration/watchdog.sh`) monitors running changes for stuck/spinning patterns and escalates through 4 levels:

- **L1**: warn
- **L2**: resume (send SIGCONT / re-trigger loop)
- **L3**: kill Ralph PID + resume in same worktree
- **L4+**: salvage partial work + mark `failed`

Additionally, `_watchdog_check_progress()` independently detects:
- **Spinning**: 3+ consecutive no_op iterations → `failed`
- **Stuck**: 3+ iterations without commits → `pause`

The problem: both L4 and spinning lead to `failed`, which is terminal. The change requires a full replan cycle (~500K+ tokens) or manual intervention to recover. Production runs show this happens 1-3 times per orchestration run (MiniShop admin-auth: 3x manual restart, sales-raketa stalls).

The dispatcher (`dispatch_change()`) already handles creating fresh worktrees, bootstrapping them, building proposals, and launching Ralph. This infrastructure can be reused for re-dispatch.

## Goals / Non-Goals

**Goals:**
- L3 escalation and spinning detection trigger re-dispatch to a fresh worktree instead of immediate failure
- Failed attempt context (what went wrong, partial diff) is forwarded to the fresh agent
- Configurable `max_redispatch` limit (default: 2) after which the change truly fails
- Existing worktree is cleaned up before re-dispatch to free resources
- Event logging and status output reflect redispatch activity

**Non-Goals:**
- Agent scoring / smart worktree selection (future P1 — dispatch stays round-robin)
- Circuit breaker for API failures (separate concern, P2)
- Health classification per worktree (future P2)
- Changing the stuck/pause path (that path works — agent gets paused, cooldown, resume)

## Decisions

### D1: Insert redispatch between L3-kill and L4-fail

**Choice**: Rewrite the escalation chain to: L1 warn → L2 resume → L3 kill+redispatch → L4+ fail

**Alternative considered**: Add a new L3.5 level between existing L3 and L4. Rejected because the current L3 (kill + resume in same worktree) rarely helps — the stale context remains. Better to replace L3's behavior entirely.

**New chain**:
```
L1: warn (unchanged)
L2: resume in same worktree (unchanged)
L3: kill Ralph → cleanup old worktree → redispatch fresh (NEW)
L4+: salvage + fail (only if redispatch_count >= max_redispatch)
```

### D2: Spinning detection also triggers redispatch (not immediate fail)

**Choice**: When `_watchdog_check_progress()` detects the spinning pattern (3+ no_op iterations), it checks `redispatch_count` before deciding to fail or redispatch.

**Rationale**: Spinning often means the agent misunderstood the task or got into a prompt loop. A fresh context is exactly what fixes this. Only after N redispatch attempts should it truly fail.

### D3: Forward failure context to fresh agent

**Choice**: Build a `retry_context` string containing:
1. Why the previous attempt failed (spinning/stuck/timeout pattern)
2. Partial diff summary (file list, not full patch — keep context small)
3. Iteration count and token usage of the failed attempt

This gets stored in `state.json` as `retry_context` and is injected into the fresh proposal by `dispatch_change()`.

**Alternative considered**: Forward the full partial-diff.patch. Rejected because the patch can be large and pollutes the fresh agent's context. File names are sufficient for the agent to know what was attempted.

### D4: Cleanup old worktree before re-dispatch

**Choice**: Call `wt-close <change_name> --force` to remove the old worktree and branch, then let `dispatch_change()` create a fresh one.

**Rationale**: Leaving the old worktree around wastes disk space and the stale branch can conflict with the new one. The salvage step (partial-diff.patch) already preserved any useful work before cleanup.

### D5: Use existing `dispatch_change()` for re-dispatch

**Choice**: The new `redispatch_change()` function is a thin wrapper: increment `redispatch_count` → salvage partial work → cleanup worktree → reset change status to `pending` → let `dispatch_ready_changes()` pick it up naturally in the next monitor cycle.

**Alternative considered**: Call `dispatch_change()` directly from the watchdog. Rejected because it couples the watchdog to the dispatcher and bypasses the normal dispatch queue. Setting status to `pending` and letting the monitor loop dispatch it is cleaner and respects `max_parallel` limits.

### D6: New `max_redispatch` directive (default: 2)

**Choice**: Configurable in `orchestration.yaml` directives. Default 2 means a change gets up to 3 total attempts (1 original + 2 redispatches).

**Rationale**: 2 redispatches balances cost (each redispatch costs ~50-100K tokens) against recovery probability. After 3 total attempts, the change likely has a fundamental issue that requires human attention.

## Risks / Trade-offs

**[Risk: Token waste on hopeless changes]** → Mitigation: `max_redispatch` cap (default 2). After 3 total attempts the change fails. The retry_context helps the fresh agent avoid repeating the same mistakes, improving success probability.

**[Risk: Worktree cleanup race condition]** → Mitigation: Kill Ralph PID first, wait 2s for process cleanup, then close worktree. The existing L3 kill logic already handles this sequence.

**[Risk: Redispatch during merge-blocked]** → Mitigation: Only redispatch changes in `running` or `dispatched` status. Changes that are `merge-blocked`, `verifying`, or `paused` are not eligible for redispatch.

**[Risk: Monitor cycle timing]** → After setting status to `pending`, the change won't be re-dispatched until the next monitor cycle (~30s). This is acceptable — a brief cooldown before retry is desirable.

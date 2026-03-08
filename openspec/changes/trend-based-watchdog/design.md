## Context

The orchestration watchdog enforces per-change token budgets via complexity-based fixed limits (S=2M, M=5M, L=10M, XL=20M). At 100% it pauses, at 120% it fails the change. E2E testing revealed this is fundamentally flawed: every budget-triggered action was a false positive where the agent had completed or was completing its work. The token count correlates with task complexity but not with whether the agent is wasting resources.

Meanwhile, Ralph (the loop engine) already has robust self-detection: idle (identical output 3x), stall (no commits 2x), and repeated commit messages. The watchdog also has hash ring loop detection. What's missing is a watchdog-level progress check that reads Ralph's own iteration data to make informed decisions.

Two layers of token safety nets exist at the orchestrator level and remain untouched:
- `token_budget` directive: stops dispatching new changes when global total exceeds budget
- `token_hard_limit` directive (default 20M): triggers a checkpoint requiring human approval

## Goals / Non-Goals

**Goals:**
- Replace per-change fixed token limits with progress-based trend detection
- Detect "spinning" (agent doing nothing productive) and "stuck" (agent trying but failing) patterns
- Use data Ralph already produces (loop-state.json iterations) — no new instrumentation needed
- Keep the watchdog as a safety net for when Ralph's self-detection doesn't trigger

**Non-Goals:**
- Implementing project-level token usage learning (future work)
- Changing Ralph's own idle/stall detection logic
- Modifying global orchestrator-level token_budget or token_hard_limit
- Adding new fields to loop-state.json

## Decisions

### D1: Read iterations array from loop-state, no new data needed

Ralph already writes rich iteration data to loop-state.json:
```json
{
  "iterations": [
    {"n": 1, "commits": ["abc"], "no_op": false, "done_check": false},
    {"n": 2, "commits": [],      "no_op": true,  "done_check": false}
  ]
}
```

The watchdog reads this directly. No new fields, no new protocol between Ralph and watchdog.

**Alternative considered**: Adding a "progress_score" field that Ralph computes. Rejected because it adds coupling — the watchdog should make its own assessment from raw data.

### D2: Two patterns — spinning and stuck

**Spinning** (3+ consecutive completed iterations with `no_op=true` AND empty commits):
The agent is running but producing nothing. Not even dirty files. This is hopeless — fail the change.

**Stuck** (3+ consecutive completed iterations with empty commits but `no_op=false`):
The agent is doing something (reading files, editing) but not committing. Could be artifact creation (ff) that's looping, or failed implementations being reverted. Pause and notify human.

**Why 3?**: Matches Ralph's own `max_idle_iterations` default. One bad iteration is normal. Two is concerning. Three is a pattern.

**Alternative considered**: Scoring system (weighted sum of signals). Rejected as over-engineered — simple pattern matching on the last N iterations is sufficient and debuggable.

### D3: Only examine completed iterations, require minimum 2

The watchdog polls every 15 seconds. Ralph iterations can take minutes. If we examine `current_iteration` while it's still running, we'd make decisions on incomplete data.

Only look at the `iterations` array (completed iterations). Require at least 2 completed iterations before making any progress judgment — the first iteration is always artifact creation overhead.

### D4: Remove complexity-based budget entirely

Remove `_watchdog_check_token_budget()`, `_watchdog_token_limit_for_change()`, and the S/M/L/XL case statement. The progress check replaces their function.

The global `token_hard_limit` (default 20M) serves as the runaway protection at orchestrator level.

### D5: Progress check runs after escalation check, not instead of it

The new `_watchdog_check_progress()` replaces `_watchdog_check_token_budget()` at the same call site (end of `watchdog_check()`). The existing hash ring detection and escalation chain remain independent — they handle different failure modes (hash ring detects poll-level sameness, progress check detects iteration-level patterns).

## Risks / Trade-offs

**[Risk] Agent that commits garbage repeatedly** → Not caught by progress check (has commits). Mitigated by: Ralph's own done_check, max_iterations limit, and code review gate.

**[Risk] Legitimate slow first iteration with no data** → Progress check requires 2+ completed iterations, so first iteration is never judged. Long first iterations are already handled by the existing PID-alive check.

**[Risk] Removing budget removes cost visibility** → The orchestrator still tracks and displays `tokens_used` per change. The `token_hard_limit` checkpoint provides human approval gates. Only the automated kill-on-limit is removed.

**[Risk] ff iterations produce no commits but create artifacts** → ff iterations write `no_op=false` (dirty files exist) and `commits=[]`. After 3 such iterations, the stuck pattern fires. This is acceptable: the stuck detection pauses (not fails), and a human can resume. Legitimate ff sequences rarely exceed 2 iterations without a commit. If they do, pausing for review is the right call.

**[Risk] Human resumes a paused change but watchdog re-pauses immediately** → The old iteration data still shows the stuck pattern. Mitigation: on resume, `resume_change()` records a `progress_baseline` (current iteration count). The progress check only examines iterations after this baseline. This gives the resumed change 3 fresh iterations before re-evaluation.

**[Risk] Escalation chain fails a change, then progress check runs in same poll cycle** → The progress check re-reads the change's current status from state before acting. If already `"failed"` or `"paused"`, it skips.

**[Risk] TOCTOU race: Ralph writes done between progress read and action] → The progress check re-reads loop-state status immediately before calling pause/fail, matching the guard pattern from the old budget check.

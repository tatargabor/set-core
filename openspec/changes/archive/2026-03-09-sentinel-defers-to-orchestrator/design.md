## Context

The sentinel is a Claude Code skill (`.claude/commands/wt/sentinel.md`) — a prompt-only component with no executable code. It instructs the Claude agent how to supervise `set-orchestrate` runs. Currently, the sentinel's crash recovery logic treats all orchestrator exits as potential problems requiring diagnosis and restart. In practice, many situations the sentinel encounters are orchestration-level issues (merge-blocked, verify failures, replan cycles) that the orchestrator already handles on its next run. The sentinel wastes tokens diagnosing these and sometimes interferes by modifying state.

Real-world problems observed across multiple E2E orchestration runs:
1. Sentinel tried to manually resolve merge-blocked changes — orchestrator now has jq deep-merge in `wt-merge`
2. Sentinel diagnosed verify failures as crashes — orchestrator has `max_verify_retries` built in
3. Sentinel spent ~50K tokens reading logs and state for situations that resolved automatically on restart
4. Sentinel modified orchestration state directly, bypassing the orchestrator's state machine

## Goals / Non-Goals

**Goals:**
- Define a clear classification: "orchestrator handles this" vs "needs human intervention"
- Reduce sentinel token waste on unnecessary diagnosis
- Prevent sentinel from interfering with orchestrator's built-in recovery mechanisms
- Keep sentinel's role to: start, poll, auto-approve periodic checkpoints, restart on process crashes, report on completion/failure

**Non-Goals:**
- Adding new sentinel capabilities (watchdog, events, etc.) — that's a separate change
- Removing crash restart entirely — process-level crashes still need sentinel restart
- Improving merge retry intelligence or planner ordering — those are incremental improvements on existing implementations

## Decisions

### 1. Two-tier classification in the sentinel prompt

Add a "Deference Principle" section that classifies situations:

**Tier 1 — Defer to orchestrator (sentinel does nothing):**
- merge-blocked changes → orchestrator's `retry_merge_queue` with jq deep-merge handles this
- verify/test failures → orchestrator's `max_verify_retries` and fix cycles handle this
- replan cycles → orchestrator's built-in replan logic handles this
- individual change failures → orchestrator marks them failed and continues with others
- token hard limit checkpoint → sentinel already asks user (non-periodic checkpoint)

**Tier 2 — Sentinel acts:**
- Process crash (SIGKILL, OOM, broken pipe, SIGPIPE) → restart after 30s
- Process hung (stale state >120s, PID alive, no log activity) → report to user
- Non-periodic checkpoint (budget_exceeded, too_many_failures) → ask user
- All changes done/failed → produce completion report

**Rationale:** The orchestrator already has recovery mechanisms for Tier 1 situations. Sentinel intervention adds no value and risks state corruption.

### 2. Simplify EVENT:process_exit handling

Current handler reads 50 lines of logs and tries to classify errors. New approach:

1. Check state.json status — if `done`, `stopped`, or `time_limit` → normal exit, report
2. Check if the orchestrator ran less than 5 minutes → rapid crash, increment counter
3. If rapid_crashes < 5 → restart (no diagnosis needed, the orchestrator will resume from state)
4. If rapid_crashes >= 5 → stop, read last 50 log lines, and report

Remove the elaborate error classification (recoverable vs fatal vs unknown). The orchestrator saves state before exit, so a simple restart is almost always correct. The only exception is rapid crashes, which indicate a systemic problem.

### 3. Remove state modification from sentinel

Current sentinel resets state from `running` to `stopped` before restart. This is unnecessary — the orchestrator's `cmd_start` already handles stale `running` state on resume. Remove this to prevent sentinel from touching state.json beyond reading it.

Exception: auto-approving periodic checkpoints (writing `approved: true`) is kept — this is the one legitimate state write.

### 4. wt-loop API error detection and backoff

Currently wt-loop has a blind 2-retry mechanism with fixed 30s wait for any non-zero claude CLI exit code. It cannot distinguish between "API temporarily unavailable" (429, 503, connection reset) and "actual bug in the code" or "loop stalled". When API goes down, the loop burns iteration budget until the watchdog's stall detection kicks in.

**New approach:**

1. Parse claude CLI exit code + stderr output after each iteration
2. Detect API-specific patterns:
   - Exit code + stderr containing `429`, `rate limit`, `overloaded`, `503`, `connection reset`, `ECONNRESET`
3. When API error detected → set loop status to `waiting:api`
4. Exponential backoff: 30s → 60s → 120s → 240s (matching sentinel's BACKOFF_BASE/BACKOFF_MAX)
5. After backoff, retry the iteration (not a new iteration — same prompt)
6. Reset backoff on successful iteration
7. After max backoff attempts (e.g., 10), set status to `stalled` with reason `api_unavailable`

**Stderr capture mechanism:**
The current claude invocation in engine.sh uses `2>&1 | tee` which merges stderr into stdout. Rather than restructuring the pipe, `classify_api_error()` should parse the per-iteration log file (`$iter_log_file`) after the invocation exits. The log already contains all stderr output. Pattern: after capturing `claude_exit_code`, grep `$iter_log_file` for API error patterns. This avoids changing the invocation pipe.

**Interaction with existing retry loop:**
engine.sh already has a 2-retry inner loop (30s fixed wait) for generic claude errors. The API backoff REPLACES this for API-specific errors:
- After claude exits non-zero, call `classify_api_error "$iter_log_file" "$claude_exit_code"`
- If API error → enter exponential backoff (separate from the 2-retry loop)
- If non-API error → use existing 2-retry mechanism as-is
The two paths are mutually exclusive per invocation.

**Integration points:**
- `lib/loop/engine.sh` — add `classify_api_error()`, call it before existing retry logic, add backoff loop
- `bin/wt-loop` — add `waiting:api` to status display in `cmd_status` case block (icon: "⏳")
- `lib/orchestration/watchdog.sh` — add `waiting:api` to TWO guards:
  1. `_watchdog_check_progress()` line ~261: add to `failed|paused|waiting:budget` case → skip
  2. `_watchdog_action_hash()` line ~225: skip hash recording when loop status is `waiting:api`
- Sentinel prompt — mention `waiting:api` in Tier 1 list (informational — sentinel poll doesn't surface loop-level status, but this documents the principle)

**Why not in sentinel?** The sentinel supervises the orchestrator process, not individual loops. API errors happen at the loop level (claude CLI invocation). The sentinel should recognize `waiting:api` status but doesn't need to act on it.

## Risks / Trade-offs

**[Risk] Sentinel ignores a real problem that needs intervention** → The sentinel still reports on completion and catches process crashes + rapid crash loops. For orchestration-level issues, the user can always check status manually. The orchestrator's own logging captures everything.

**[Risk] Removing error classification loses diagnostic value** → The completion report already includes all change statuses and the log file is preserved. Detailed diagnosis is better done by the user post-run, not by the sentinel burning tokens mid-run.

**[Trade-off] Less proactive → more efficient** → The sentinel becomes more passive, which means some issues persist longer before human intervention. But observed E2E runs showed that sentinel intervention made things worse, not better.

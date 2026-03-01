## Context

The v5 orchestration run (5 changes, 75 min, 3.3M tokens) revealed six issues:
1. Merge conflict resolution wastes tokens trying sonnet on large conflicts that always time out
2. Stale loop-state check logs 100+ identical "PID alive" messages per run
3. Parallel changes modifying shared files (conventions docs) cause guaranteed merge conflicts
4. Replan cycle transitions are invisible in logs and TUI
5. TUI token counter flashes to zero during replan state reinit
6. No crash recovery — if orchestrator dies, everything stops

Current code: `bin/wt-merge` (merge model selection), `bin/wt-orchestrate` (monitor loop, planner prompt, cycle transitions), `gui/tui/orchestrator_tui.py` (token display).

## Goals / Non-Goals

**Goals:**
- Reduce wasted tokens on merge conflicts that sonnet cannot handle
- Eliminate log noise from stale warnings when agent is actually working
- Give planner awareness of shared resource contention
- Make cycle boundaries explicit in logs and TUI
- Keep token counter stable across replan transitions
- Add minimal crash recovery without extra LLM cost

**Non-Goals:**
- Tier 2 trivial merge automation (list/array/import merges) — future work
- Full sentinel agent with its own LLM — too expensive, not justified yet
- TUI redesign or new panels — just fix the token flash
- Automated shared resource detection from file analysis — planner hint is sufficient

## Decisions

### 1. Size-based merge model selection

**Decision:** If the total conflict hunk lines exceed 200, skip sonnet and go directly to opus.

**Why:** Sonnet consistently times out on 900+ line files (300s). Trying it first wastes ~10K tokens and 300s. Small conflicts (<200 lines) are well within sonnet's capacity.

**Alternative considered:** Always use opus for merges. Rejected because small conflicts are common and sonnet is 5x cheaper.

**Implementation:** In `llm_resolve_conflicts()`, compute `total_lines` before the LLM call (already tracked), then branch:
```
if total_lines > 200 → opus directly (600s timeout)
else → sonnet first (300s), opus fallback on failure
```

### 2. Stale warning debounce via log level

**Decision:** Change the "loop-state stale but PID alive" message from `log_info` to `log_debug`.

**Why:** This message fires every 15s poll when an iteration takes >5 minutes (normal for opus). With `log_debug`, it still appears in the full log but not in the console or TUI. Rate-limiting was considered but adds state tracking complexity for no user benefit — the message is simply not actionable.

**Alternative considered:** Rate-limit to once per 5 minutes per change. Rejected: adds a `last_stale_log_time` field per change in state, extra code for the same result.

### 3. Shared resource planner hint

**Decision:** Add ~6 lines to both decomposition prompts (spec-mode and brief-mode) warning about shared file contention.

**Why:** The planner doesn't know about file-level contention. A simple hint is enough — the LLM already reasons about dependencies. We don't need automated detection (which would require predicting file paths from scope descriptions).

**Prompt addition:**
```
SHARED RESOURCE RULE:
If 2+ changes would likely modify the same shared file (conventions docs,
shared types, config files, common UI components), chain them via
depends_on to prevent merge conflicts. Prefer serialization over
parallel execution when shared files are involved.
```

### 4. Cycle boundary markers

**Decision:** Three additions:
1. Log separator: `log_info "========== REPLAN CYCLE $cycle =========="` at cycle start
2. State field: `cycle_started_at` ISO timestamp, set during `auto_replan_cycle()`
3. TUI: show cycle boundary as a highlighted line in the log panel

**Why:** Currently the only indicator is "Plan v1 (replan #2)" in the header. The log has no visible boundary between cycles. A developer reviewing a run cannot tell when one cycle ended and the next began.

### 5. TUI token persistence

**Decision:** In `_update_header()`, read `prev_total_tokens` immediately (already done) but also handle the race condition where `init_state()` has been called but current cycle tokens haven't been computed yet. If `current_tokens == 0` and `prev_total_tokens > 0`, display `prev_total_tokens` with a "+" prefix to indicate "at least this many".

**Why:** During the brief window between `init_state()` and the first poll that computes new tokens, the counter shows "0" or "-". This is confusing because it looks like tokens were lost.

**Implementation:** ~3 lines in `_update_header()`:
```python
if current_tokens == 0 and prev_tokens > 0:
    total_tokens = prev_tokens  # show previous total until new data arrives
```

### 6. Sentinel as minimal bash wrapper

**Decision:** Create `bin/wt-sentinel` — a ~35 line bash script that:
1. Wraps `wt-orchestrate start "$@"` in a supervised loop
2. On exit code 0 + state `done`: stop (orchestration complete)
3. On exit code 0 + state `stopped`: stop (user Ctrl+C, don't restart)
4. On non-zero exit + no SIGINT: log, wait 30s, restart
5. Before restart: fix stale state (`running` → `stopped` if no live process)
6. Max 5 rapid crashes (within 5 min each) before giving up
7. SIGINT/SIGTERM: forward to child, don't restart, exit cleanly
8. Write PID to `sentinel.pid` for external monitoring

**Key insight from v5:** The orchestrator didn't crash during v5 — it stopped on merge-blocked (a proper state). The actual problems (merge timeout, build break) are now handled by internal fixes. The sentinel is a safety net for rare crashes (OOM, jq segfault on malformed JSON), not the primary recovery mechanism.

**Why not an LLM-powered runner agent:** Considered an Opus agent that monitors events and fixes issues autonomously. Rejected for now — v5 showed 1 minute of manual intervention in 75 minutes. The cost of a continuous Opus supervisor doesn't justify the savings yet. If future runs show recurring failures that the internal fixes can't handle, an event-driven runner agent (reacting to `send_notification()` events via a JSONL stream) would be the next evolution.

**Alternative considered:** `wt-loop` as runner (reusing existing iteration infrastructure). Rejected: overcomplicates wt-loop's simple purpose, and the sentinel's job is fundamentally different (process supervision vs task iteration).

## Risks / Trade-offs

- [Shared resource hint may over-serialize] → Mitigated: it's a hint, not a hard rule. The LLM can ignore it if parallelism is clearly safe.
- [200-line threshold for model selection is arbitrary] → Mitigated: based on empirical data (v5 had 900+ line conflicts that timed out). Can be adjusted via future tuning.
- [Sentinel restart loop on persistent crash] → Mitigated: max 5 restarts with 30s backoff. After that, human intervention is needed anyway.
- [TUI token display showing stale `prev_total_tokens`] → Acceptable: brief window (one poll cycle, ~3s) with "at least" semantics is better than showing 0.

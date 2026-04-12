# Design: fix-activity-timeline-claude-coverage

## Context

The parent `activity-timeline` change (implemented, not yet archived) built the Gantt-style Activity view, the `GET /api/{project}/activity-timeline` endpoint, and the event instrumentation gaps (IDLE_START/END, WATCHDOG_ESCALATION, ITERATION_START/END, CONFLICT_RESOLUTION_*). That work is sound — the skeleton is good. This change fills in the missing time categories that make the view useful.

### Evidence from a real 8h run

A single orchestration run (8h 05m wall time, 8 changes processed sequentially, `parallel_efficiency = 0.99x`) produced 6458 events. Parsing them gives:

| Source                                 | Time         | Currently visible? |
|----------------------------------------|--------------|--------------------|
| Agent sessions (DISPATCH → CHANGE_DONE) | 5h 57m (74%) | no                 |
| Orchestrator LLM (review, spec_verify, replan, classify) | 1h 58m (24%) | no |
| Gates (build, test, e2e, dep-install)  | 3m 36s       | yes                |
| Merge                                  | <1s          | yes                |
| Overhead                               | ~6m          | —                  |

The sum accounts for ~7h 59m of the 8h 05m wall time — nothing is secretly parallel, nothing is hidden. The aggregator just doesn't know about `LLM_CALL` events and has no fallback for the missing `STEP_TRANSITION` signal.

## Goals / Non-Goals

**Goals:**
- Make every minute of Claude CLI work visible in the Activity view (agent sessions + orchestrator LLM calls + sentinel LLM calls)
- Keep the change data-only (no engine modifications) so it's safe to ship against a running orchestration
- Preserve the existing span format and API contract — only add new categories and new event handlers
- Keep sentinel work visually separate so users understand which time is parallel and which is serial

**Non-Goals:**
- Fixing the `_set_step()` dead code in the engine (separate change, hot path)
- Per-turn session granularity from the Claude projects jsonl files (expensive, later)
- Cost aggregation from LLM_CALL.cost_usd (orthogonal)
- Historical backfill — the new code works on any event log, old or new, because it's pure aggregation over JSONL

## Decisions

### 1. `LLM_CALL` start time is computed retroactively

`LLM_CALL` events are emitted **after** the subprocess returns, so the event timestamp is the *end* of the call. Start is derived as `ts - duration_ms`.

**Why this is correct:** `run_claude_logged()` in `lib/set_orch/subprocess_utils.py:322` wraps `run_claude()` and emits the event in a `try` block immediately after the call returns (line 350-363). The `duration_ms` field is the measured wall time of the subprocess.

**Edge case:** If multiple `LLM_CALL`s happen back-to-back for the same change, their computed start times may overlap slightly if the event-emit overhead is large. Not a real problem — span overlap is already handled by the Gantt renderer (opacity/stacking).

### 2. DISPATCH-based implementing span (fallback only)

The implementing span is built from `DISPATCH` events with this state machine:

```
DISPATCH(change=X)        → open implementing span for X
CHANGE_DONE(change=X)     → close implementing span for X
DISPATCH(change=X) again  → close previous implementing span for X (= redispatch)
MERGE_START(change=X)     → close implementing span for X (agent done, merge pipeline taking over)
end of stream             → close any open implementing span at last event ts
```

`STEP_TRANSITION` events take precedence: if any are seen for a change, the DISPATCH fallback is disabled for that change and the existing `open_steps` logic runs. This makes the fix forward-compatible — when `_set_step()` is eventually wired up, the finer-grained step breakdown kicks in automatically.

**Why not just wait for `_set_step()` to be fixed:** touching the engine while a long-running orchestration is active is risky (per the `no-modify-during-run` feedback memory). Data-only path is safe and gives 99% of the value.

### 3. Sentinel LLM spans on a separate lane (not mixed with orchestrator LLM)

Sentinel events get `category = f"sentinel:llm:{purpose}"`, not `llm:{purpose}`. This keeps the sentinel lane visually distinct and prevents users from thinking the orchestrator LLM time is higher than it actually is.

**Alternative considered:** Mix sentinel LLM calls into the same `llm:*` categories. Rejected — sentinel is always-on supervisor work, conceptually different from pipeline work. Users asked for clarity on "what else is running", which means sentinel should be visible *and* distinguishable.

### 4. Span-coverage-aware idle gap detection

Current `_detect_idle_gaps()` (activity.py:387-443) walks event pairs and calls `_is_covered()` per gap, but `_is_covered()` only checks if an existing span *strictly contains* the gap (`rs <= gap_start_ms and re >= gap_end_ms`). Partial overlaps are not detected — e.g., an implementing span from 01:00 to 02:00 and a gap from 01:30 to 02:30 triggers a false idle.

New approach: compute the **union of all span intervals** after span building, then walk the time range of the run and emit idle spans only for intervals not touched by any span.

**Algorithm:** sort spans by start time, merge overlapping/adjacent intervals into a union list, then walk gaps between merged intervals; any gap > 60s becomes idle. O(n log n).

**Why over per-gap check:** simpler, correct for partial overlap, cheaper (one sort + one pass instead of nested loop).

### 5. No new event types

This change adds **zero new event emissions**. It only reads existing events more carefully. This is deliberate:
- no risk of breaking the event schema
- no risk to running orchestrations
- rollback is trivial (revert the file)

## Risks

**R1: DISPATCH span may overestimate agent work time**  
If an agent dispatch fails early (crash, timeout) without emitting `CHANGE_DONE`, the implementing span runs to end-of-stream, making the breakdown look like the agent spent the rest of the run on one change. Mitigation: close implementing spans also on `STATE_CHANGE to=failed`, `STATE_CHANGE to=pending`, `WATCHDOG_ESCALATION action=fail`. Also close on ralph-crash style events.

**R2: Sentinel filter skew**  
`_detect_idle_gaps()` excludes sentinel events from gap calculation — that's correct (sentinel polling shouldn't count as pipeline activity). But if sentinel LLM spans also get emitted, they'd add to `activity_time_ms` and inflate `parallel_efficiency`. Mitigation: treat sentinel LLM spans as present on the lane but exclude from the `activity_time_ms` sum, or add a separate `sentinel_time_ms` metric. **Decision: include in `activity_time_ms`** — that's what `parallel_efficiency` should reflect (sentinel IS parallel real work). Label the metric as "includes sentinel" in the UI header.

**R3: Overlap between implementing and verifier LLM**  
A `review` LLM_CALL may fire while the change is still in `DISPATCH → CHANGE_DONE` window (verifier can run inside the session?). If both spans exist, breakdown sums them and `activity_time_ms > wall_time_ms`. This is **correct** behavior — `parallel_efficiency > 1.0` means there was genuine parallel work. Document this in the UI header tooltip.

## Alternatives Considered

### A1: Wire up `_set_step()` in the engine

Would eliminate the need for the DISPATCH fallback and give finer grain (planning/implementing/fixing). Rejected for this change because:
- touches hot engine code during active orchestrations
- requires decisions about when to mark planning vs implementing vs fixing (currently no clear signal)
- the DISPATCH fallback gives 100% of the wall-time coverage we need right now

Should be a follow-up change.

### A2: Parse per-turn timestamps from Claude session jsonl files

Would give millisecond-accurate agent turn timing. Rejected because:
- requires scanning `~/.claude/projects/<wt>/*.jsonl` per request
- makes the endpoint slow on projects with many sessions
- the current DISPATCH-based span is accurate at the "session wall time" level, which is what matters for "where did the time go"

Should be a follow-up enhancement (maybe as a separate endpoint `/api/{project}/activity-timeline/detail`).

### A3: Emit `AGENT_SESSION_START/END` events explicitly

Would add a clean signal instead of inferring from DISPATCH/CHANGE_DONE. Rejected because:
- adds new event types, which requires engine changes
- the DISPATCH/CHANGE_DONE pair is already sufficient and well-defined
- we want this change to be data-only

## Rollout

1. Implement backend changes in `activity.py`
2. Add unit tests for each new span builder and the new gap detection
3. Update frontend color map + category order
4. Manually verify against a completed run (use a run log where you already know the time breakdown)
5. Deploy; no restart of running orchestrations needed (the endpoint re-reads events on each request)

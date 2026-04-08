# Design: activity-timeline

## Context

The orchestration engine already emits structured events (STATE_CHANGE, GATE_START, GATE_PASS, MERGE_START, MERGE_COMPLETE, STEP_TRANSITION, LLM_CALL) to a JSONL file via the EventBus. Sentinel events live in a separate `.set/sentinel/events.jsonl`. Per-worktree loop state tracks iteration start/end in `loop-state.json`. Gate durations are recorded as `gate_*_ms` fields on each change.

The web dashboard is a Vite SPA (React + TypeScript + Tailwind + recharts) with a tab system in `Dashboard.tsx`. Adding a tab requires: extending the `PanelTab` union type, adding to the tabs array, and rendering a component conditionally.

## Goals / Non-Goals

**Goals:**
- Reconstruct a complete activity timeline from existing event sources
- Fill instrumentation gaps with new events (not refactoring the event system)
- Provide a scrollable, zoomable Gantt-style visualization with per-category swim lanes
- Show where time goes at a glance (breakdown summary)

**Non-Goals:**
- Unifying the EventBus and sentinel event systems (future work)
- Real-time streaming updates (periodic refresh is sufficient)
- Per-worktree separate Gantt lanes (aggregated view only)
- Sub-second granularity (30s buckets are sufficient)

## Decisions

### 1. Span-based data model (not bucket-first)

The backend reconstructs **spans** — contiguous time intervals with a category and change name — from events. A span starts when an event signals the beginning of an activity (e.g., GATE_START) and ends when the corresponding end event fires (GATE_PASS) or state transitions away.

**Why over pure bucketing:** Spans preserve exact timing, retry counts, and per-change attribution. The frontend can render them directly as Gantt bars. Bucket aggregation is computed from spans for the summary breakdown.

**Alternative considered:** Computing only 30s buckets server-side. Rejected because it loses the ability to show individual gate runs, retries, and hover details.

### 2. Multi-source event merging (not unified bus)

The aggregator reads from three sources and merges by timestamp:
1. `orchestration-events.jsonl` (+ rotated archives) — state changes, gates, merges
2. `.set/sentinel/events.jsonl` — sentinel lifecycle (crash, restart, poll)
3. Per-worktree `loop-state.json` — iteration boundaries

**Why not refactor to unified bus:** The sentinel event system works fine for its purpose. Merging at query time is simpler and doesn't require touching running orchestrations.

### 3. Category taxonomy

Fixed set of activity categories, each gets its own swim lane:

| Category | Source Event(s) |
|---|---|
| `planning` | STEP_TRANSITION to=planning |
| `implementing` | STEP_TRANSITION to=implementing |
| `fixing` | STEP_TRANSITION to=fixing |
| `gate:build` | GATE_START(build) → GATE_PASS(build) |
| `gate:test` | GATE_START(test) → GATE_PASS(test) |
| `gate:review` | GATE_START(review) → GATE_PASS(review) |
| `gate:verify` | GATE_START(verify) → GATE_PASS(verify) |
| `gate:e2e` | GATE_START(e2e) → GATE_PASS(e2e) |
| `gate:smoke` | GATE_START(smoke) → GATE_PASS(smoke) |
| `gate:scope-check` | GATE_START(scope_check) → GATE_PASS(scope_check) |
| `gate:rules` | GATE_START(rules) → GATE_PASS(rules) |
| `merge` | MERGE_START → MERGE_COMPLETE |
| `idle` | IDLE_START → IDLE_END (new) |
| `stall-recovery` | WATCHDOG_ESCALATION (new) |
| `dep-wait` | STATE_CHANGE to=dep-blocked → away |
| `manual-wait` | MANUAL_STOP → MANUAL_RESUME (new) |
| `sentinel` | sentinel poll events (overhead estimation) |

### 4. Parallel worktree handling

When multiple worktrees are active simultaneously, each contributes to its category independently. On the Gantt, overlapping spans within the same category show intensity (opacity/thickness) indicating parallelism count. The breakdown sums all activity time, so total activity time may exceed wall time — this is expected and the "parallel efficiency" ratio (activity_time / wall_time) shows utilization.

### 5. Frontend: horizontal scroll + zoom (video editor style)

The Gantt renders as a fixed-height panel with:
- Time axis on top, horizontally scrollable
- Category labels fixed on the left (sticky)
- Zoom controls that adjust the time-per-pixel ratio
- Terminal/monospace text aesthetic matching the existing dashboard
- No recharts for the Gantt itself (custom SVG/canvas for horizontal bar rendering) — recharts lacks native Gantt support
- recharts BarChart for the breakdown summary

### 6. Backend computation, not frontend

The aggregator runs server-side. The JSONL files can be large (1MB+ with rotation). The API returns pre-computed spans and breakdown. The frontend only renders.

## Risks / Trade-offs

**[Risk] Event gaps in older runs** → Runs completed before the new instrumentation events won't have idle/manual-stop/iteration spans. Mitigation: the aggregator infers "unknown" spans from gaps between known events, displayed as a faded category.

**[Risk] Large event files slow the endpoint** → Mitigation: the endpoint accepts `from`/`to` time range params to limit scanning. Rotated archives older than the range are skipped.

**[Risk] Custom SVG Gantt complexity** → Mitigation: keep it simple — horizontal colored bars per lane, no drag/resize, minimal interaction (hover tooltips only). The existing dashboard already uses custom rendering in several components.

## Open Questions

- Should the Activity tab auto-scroll to "now" on first load during live runs? (Probably yes.)
- Should there be a "focus on change" filter that highlights spans for a single change? (Nice-to-have, not MVP.)

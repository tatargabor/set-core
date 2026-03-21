# Design: timeline-iteration-blocks

## Context

The current timeline shows STATE_CHANGE events as blocks: `pending → running → verify → merged`. But a change can have 30+ loop iterations within a single "running" block — all invisible. The iteration data exists in `loop-state.json` but isn't exposed in the timeline API.

The user wants iterations as the primary visual unit, with state changes shown as color/marker transitions between iteration blocks.

## Goals / Non-Goals

**Goals:**
- Merge iteration data (from loop-state.json) with state transitions (from events JSONL) into a unified timeline
- Render each iteration as a small block, colored by the state it belongs to
- Show state boundaries as separators between iteration blocks
- Preserve fallback for non-Ralph changes (state-only view)

**Non-Goals:**
- Click-through to iteration logs
- Live-updating timeline
- Team mode sub-iteration visualization

## Decisions

### D1: State assignment algorithm

Each iteration gets the state that was active when it started. Algorithm:

```python
# Sort transitions by timestamp
# For each iteration, binary search for the latest transition where ts <= iteration.started
# That transition's "to" field is the state

def assign_states(transitions, iterations):
    sorted_trans = sorted(transitions, key=lambda t: t["ts"])
    for it in iterations:
        state = "pending"  # default before first transition
        for t in sorted_trans:
            if t["ts"] <= it["started"]:
                state = t["to"]
            else:
                break
        it["state"] = state
```

**Why:** Simple, deterministic, handles out-of-order events. No need for new event types — we reuse existing STATE_CHANGE events + loop-state.json iterations.

### D2: API response shape

Extend `ChangeTimelineData` with an `iterations` array:

```typescript
interface ChangeTimelineData {
  transitions: { ts: string; from: string; to: string }[]
  iterations: {
    n: number
    started: string
    ended: string
    state: string        // assigned from transitions
    commits: number
    tokens_used: number
    timed_out: boolean
    no_op: boolean
  }[]
  duration_ms: number
  current_gate_results: Record<string, string | number>
}
```

Empty `iterations: []` for non-Ralph changes → frontend falls back to current rendering.

### D3: Where to read loop-state.json

`_build_change_timeline()` already receives `project_path`. The loop-state.json lives at `<worktree_path>/.set/loop-state.json`. We need the worktree path for the change.

Strategy: read `orchestration-state.json` to get `worktree_path` for the change (already done for gate results), then check for `.set/loop-state.json` in that worktree.

### D4: Frontend rendering approach

```
State: running                    verify    running
       ↓                            ↓         ↓
  ┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐  │  ┌─┐  │  ┌─┐┌─┐┌─┐
  │1││2││3││4││5││6││7││8││9│  │  │10│  │  │11││12││13│
  └─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘  │  └─┘  │  └─┘└─┘└─┘
  ─────── blue ──────────────── yellow ──  ── blue ───
```

- Each iteration = small rounded square (`w-6 h-6` or similar), colored by STATE_COLORS[state]
- State boundary = thin vertical separator line + state label
- Hover tooltip with iteration details
- Wrap to next line if too many iterations (flex-wrap)
- Fallback: if `iterations.length === 0`, render current state-block view

### D5: Non-running state transitions

State transitions that happen outside of loop iterations (e.g., `pending → dispatched`) are shown as single state-colored blocks between iteration groups, same as current behavior. These appear in the flow where their timestamp falls chronologically.

## Risks / Trade-offs

- **[Risk] Large iteration counts (30+) may overflow horizontally** → Mitigation: flex-wrap, small block size (6x6px). Even 30 blocks at 24px+gap = ~900px, fits in most views.
- **[Risk] loop-state.json may be deleted after merge** → Mitigation: if file not found, return empty iterations (graceful fallback).
- **[Risk] State assignment may be wrong if events are missing** → Mitigation: default state = "running" (most common for iterations), which is a reasonable assumption.

## Open Questions

_None._

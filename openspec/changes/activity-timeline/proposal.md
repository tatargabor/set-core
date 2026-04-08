# Change: activity-timeline

## Why

There is no way to see where wall-clock time goes during an orchestration run. Token usage is tracked, but time spent on implementation, gate execution, merging, idle waiting, stall recovery, and sentinel overhead is invisible. Operators cannot answer "what ate the most time?" or "how much idle time was there?" without manually reading logs.

## What Changes

### 1. Backend: Activity timeline aggregator

New API endpoint `GET /api/{project}/activity-timeline` that reconstructs a time-based activity breakdown from existing event sources (orchestration-events JSONL, sentinel events, loop-state files). Produces a list of typed time spans and a per-category breakdown. Supports time range filtering and configurable bucket size (default 30s).

### 2. Instrumentation: fill event gaps

Add missing events to the existing EventBus where activity transitions are currently invisible:
- `IDLE_START` / `IDLE_END` — when no activity is detected (watchdog)
- `MANUAL_STOP` / `MANUAL_RESUME` — user-triggered pause/resume
- `WATCHDOG_ESCALATION` — escalation level transitions with timestamp
- `ITERATION_START` / `ITERATION_END` — Ralph loop iteration boundaries emitted to EventBus
- `CONFLICT_RESOLUTION_START` / `CONFLICT_RESOLUTION_END` — merger conflict resolution timing

### 3. Frontend: Activity tab in web dashboard

New "Activity" tab with:
- Horizontally scrollable Gantt-style timeline with per-category swim lanes (planning, implementing, fixing, gate:build, gate:test, gate:review, gate:e2e, gate:smoke, gate:scope-check, merge, idle, stall/recovery, dep-wait, manual-wait, sentinel)
- Zoomable time axis (in/out)
- Summary breakdown bar chart sorted by time spent
- Hover tooltips with span details (change name, duration, result)
- Gate retry visibility (multiple blocks on same lane with pass/fail markers)
- Auto-refresh (configurable interval) + manual refresh button
- Terminal/text visual style consistent with existing dashboard aesthetic

## Capabilities

### New Capabilities
- `activity-timeline-api` — backend aggregation endpoint
- `activity-dashboard` — frontend Activity tab

### Modified Capabilities
- `activity-tracking` — add missing event emissions for idle, manual stop/resume, watchdog escalation, iteration boundaries, conflict resolution

## Impact

- `lib/set_orch/watchdog.py` — emit IDLE_START/IDLE_END, WATCHDOG_ESCALATION events
- `lib/set_orch/dispatcher.py` — emit MANUAL_STOP/MANUAL_RESUME events
- `lib/set_orch/merger.py` — emit CONFLICT_RESOLUTION_START/END events
- `lib/set_orch/loop_state.py` — emit ITERATION_START/ITERATION_END events
- `lib/set_orch/api/` — new activity-timeline endpoint
- `web/src/pages/Dashboard.tsx` — add Activity tab
- `web/src/components/ActivityView.tsx` — new component (Gantt + breakdown)

# Proposal: timeline-iteration-blocks

## Why

The change timeline in set-web currently shows only state transitions (pending → running → verify → merged) as blocks. A change with 30 iterations inside a single "running" state shows just one "running" block — hiding the actual effort. Users need to see every iteration as a discrete visual element, with state changes shown as markers/color transitions between them, not as the primary organizational unit.

## What Changes

- **Enrich timeline API** to include per-iteration data from `loop-state.json` alongside state transitions, producing a unified timeline where each iteration is a block and state changes are boundaries between them.
- **Redesign ChangeTimelineDetail.tsx** to render iterations as individual blocks (circles/squares) in a horizontal flow, with state indicated by color and state-change boundaries marked visually (separator line + label).
- **New capability spec** for the iteration-based timeline data model and rendering.

## Capabilities

### New Capabilities
- **timeline-iterations**: Iteration-based timeline data model and rendering for change detail view.

### Modified Capabilities
_None — this replaces the existing timeline rendering without changing other specs._

## Impact

- **lib/set_orch/api.py**: `_build_change_timeline()` enriched to merge STATE_CHANGE events with iteration data from `loop-state.json`.
- **web/src/components/ChangeTimelineDetail.tsx**: Rewritten to render iteration-based blocks instead of state-transition blocks.
- **web/src/lib/api.ts**: `ChangeTimelineData` type updated with iterations array.
- No backend schema changes (loop-state.json already has all iteration data).
- No new dependencies.

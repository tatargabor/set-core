## Why

The wt-web dashboard displays changes as a flat list (ChangeTable) with no visibility into orchestration phases or dependency relationships. The backend already tracks `change.phase`, `state.extras.current_phase`, `state.extras.phases`, and `change.depends_on` — but the frontend ignores all of it. Users cannot see which phase is active, which changes belong to which phase, or why a change is blocked.

## What Changes

- Add a new **"Phases" tab** to the dashboard, alongside the existing "Changes" tab
- New `PhaseView` component that groups changes by their `phase` field and renders a dependency tree within each phase
- Phase headers showing: status (completed/running/pending), progress (done/total), aggregated tokens, aggregated duration
- Dependency tree nesting within each phase: root changes (no intra-phase deps) at top level, dependent changes nested under their parent
- Blocked changes show which dependency they're waiting on
- Extend TypeScript types (`ChangeInfo`, `StateData`) to include `phase`, `depends_on`, `current_phase`, and `phases` fields that already exist in the JSON response

## Capabilities

### New Capabilities
- `phase-tree-view`: Dashboard component that visualizes orchestration phases as a tree with dependency nesting, phase status headers, and per-phase aggregated metrics

### Modified Capabilities

## Impact

- **Frontend only** — no backend/API changes needed (data already served)
- New files: `web/src/components/PhaseView.tsx`
- Modified files: `web/src/lib/api.ts` (type extensions), `web/src/pages/Dashboard.tsx` (add tab)
- No new dependencies

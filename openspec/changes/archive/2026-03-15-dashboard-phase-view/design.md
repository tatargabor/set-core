## Context

The wt-web dashboard currently renders changes as a flat `<table>` in `ChangeTable.tsx`. The backend state already contains all phase and dependency data (`change.phase`, `change.depends_on`, `state.extras.current_phase`, `state.extras.phases`) — it's served via `/api/{project}/state` but the frontend TypeScript types don't declare these fields and no component uses them.

Real-world orchestration runs show:
- 3-10 changes per run
- 1-3 phases
- Linear dependency chains (max 1 dependency per change, no diamond patterns)
- Phase-within changes run in parallel unless blocked by `depends_on`

## Goals / Non-Goals

**Goals:**
- New "Phases" tab showing changes grouped by phase with dependency tree nesting
- Phase-level summary (status, progress, tokens, duration)
- Dependency visibility: which change blocks which, within a phase
- Works for single-phase runs (most common case) and multi-phase runs

**Non-Goals:**
- No interaction (stop/skip buttons) — the Changes tab handles that
- No log panel integration — Phases tab is a read-only overview
- No DAG visualization — empirical data shows linear chains only, tree nesting suffices
- No cross-phase dependency annotation — phase ordering makes it implicit

## Decisions

### 1. Separate tab, not inline in ChangeTable

The ChangeTable is a flat sortable table — good for quick status scanning. The PhaseView is a tree — good for understanding execution structure. Different mental models, different components. Adding phase grouping inside ChangeTable would complicate its already-complex mobile/desktop split.

Alternative considered: Collapsible phase groups in ChangeTable. Rejected because it adds complexity to a component that's already 294 lines with mobile/desktop branching.

### 2. Client-side tree computation

The dependency tree is built client-side from the flat `changes[]` array:
1. Group changes by `phase` field
2. Within each phase, find root changes (no `depends_on` within same phase)
3. Build tree: each change's children = changes in same phase whose `depends_on` includes this change's name

No API changes needed. The grouping + tree computation is trivial for 3-10 changes.

### 3. Phase status derivation

Phase status comes from two sources:
- Multi-phase: `state.extras.phases[N].status` (completed/running/pending)
- Single-phase (no `extras.phases`): derive from change statuses — all terminal = completed, any running = running, else pending

This handles the `init_phase_state()` early-return for single-phase runs where `extras.phases` is undefined.

### 4. Type extension approach

Add `phase` and `depends_on` to `ChangeInfo`, and `current_phase` + `phases` to `StateData`. These fields already exist in the JSON — we're just declaring them in TypeScript. No runtime change.

## Risks / Trade-offs

- [Single-phase overhead] A phase header wrapping all changes adds one visual level. → Acceptable: it still shows the dependency tree which is the main value.
- [Stale phase data] If orchestrator crashes mid-phase, `extras.phases` status may be stale. → PhaseView derives status from change statuses as fallback, not solely from `extras.phases`.

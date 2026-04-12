# Spec: step-progress-bar

## Capability

Each orchestrated change displays its lifecycle step (P I F M A) alongside gate results (B T R E S) on the web dashboard. The Python engine tracks `current_step` explicitly and emits `STEP_TRANSITION` events for real-time updates.

## Behavior

### Steps
- `planning` (P) — artifact creation via FF/openspec
- `implementing` (I) — agent working on tasks
- `fixing` (F) — gate retry, agent fixing failures
- `merging` (M) — integration gates + ff-only merge
- `archiving` (A) — spec sync, worktree cleanup

### State tracking
- `current_step` field on Change in orchestration-state.json
- Set at each lifecycle transition by engine/dispatcher/merger
- `STEP_TRANSITION` event emitted with from/to

### Web rendering
- StepBar component with P I F M A letter badges
- Same color scheme as GateBar: green=done, blue+pulse=current, gray=pending, amber=fixing
- Rendered alongside GateBar in ChangeTable and detail views

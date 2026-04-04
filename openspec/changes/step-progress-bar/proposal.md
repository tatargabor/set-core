# Change: step-progress-bar

## Why

The web dashboard shows gate results (B T R E S) but not the agent's lifecycle steps. Users can't see whether an agent is planning, implementing, fixing, or merging — just "running" then suddenly "merged". In craftbrew-run20, users couldn't tell if the agent was in FF artifact creation (2 min), implementation (20 min), or gate retry (45 min).

## What Changes

### 1. Python: add `current_step` field to Change state

Track the agent lifecycle as explicit steps in the orchestration state. The engine sets `current_step` at each transition:

- `planning` — FF/artifact creation phase
- `implementing` — agent working on tasks
- `fixing` — gate retry, agent fixing failures
- `integrating` — merging main into branch, running gates
- `merging` — ff-only merge to main
- `archiving` — spec sync, worktree cleanup
- `done` — terminal

### 2. Python: emit STEP_TRANSITION events

Emit `STEP_TRANSITION` event with `{change, from_step, to_step}` so the web can update in real-time.

### 3. Web: StepBar component

Display `P I F M A` badges next to the GateBar (`B T R E S`), same styling pattern:
- Green = completed
- Blue + pulse = current
- Gray = pending/not reached
- Amber = retry/fix

### 4. Web: ChangeTable integration

Render StepBar alongside GateBar in the change list and detail views.

## Impact

- `lib/set_orch/state.py` — add `current_step` field
- `lib/set_orch/engine.py` — set step at transitions
- `lib/set_orch/dispatcher.py` — set step on dispatch/resume
- `lib/set_orch/merger.py` — set step on integrate/merge/archive
- `web/src/lib/api.ts` — add `current_step` to ChangeInfo
- `web/src/components/StepBar.tsx` — new component
- `web/src/components/ChangeTable.tsx` — render StepBar
- `web/src/hooks/useWebSocket.ts` — add step_transition event

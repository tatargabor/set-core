# Change: gate-observability

## Why

The gate pipeline is a black box after smoke — the user sees a change go from "running" to "merged" or "done" with no visibility into what happened. From craftbrew-run20:

1. **Silent success**: build/test/e2e pass logs nothing — hard to verify gates actually ran
2. **No timing**: gate start/end/elapsed not logged — can't diagnose slow gates
3. **Web dashboard gaps**: GateBar doesn't handle `e2e-redispatch`, `integration-failed`, or the new `per-change-e2e-gates` events. EventFeed component exists but is never imported
4. **Merge pipeline invisible**: after gates pass, integration→merge→archive is a black box. No intermediate events emitted or rendered
5. **Session mapping weak**: user can't easily see which Claude session is active for a given change

## What Changes

### 1. Python: log every gate step with start/end/elapsed

In `merger.py` `_run_integration_gates()`, add INFO-level logs for:
- Each gate start (already exists)
- Each gate success with elapsed_ms (MISSING)
- Summary line: "Integration gates for X: 4/4 passed in 23.4s"

### 2. Python: emit granular events

Add new events for the merge pipeline phases:
- `GATE_START` — when each individual gate begins
- `GATE_PASS` — when each gate succeeds (not just VERIFY_GATE on fail)
- `MERGE_START` / `MERGE_COMPLETE` — when ff-only merge begins/ends

### 3. State: add e2e_result field

Add `e2e_result` to ChangeState alongside `smoke_result`. Currently e2e and smoke share `smoke_result` which is confusing. Separate them.

### 4. Web: GateBar handle new statuses

Update GateBar.tsx to show 'E' for E2E gate (separate from 'S' smoke). Handle `e2e-redispatch` as amber/retry icon.

### 5. Web: activate EventFeed

Import and render the existing EventFeed component. Show live gate events as they happen.

### 6. Web: merge pipeline visibility

Add a "Merge" phase to ChangeTimeline that shows integration→gates→merge steps with pass/fail/pending states.

## Impact

- `lib/set_orch/merger.py` — logging + event emission
- `lib/set_orch/state.py` — add `e2e_result` field
- `lib/set_orch/api/orchestration.py` — expose new field
- `web/src/components/GateBar.tsx` — new gate type + statuses
- `web/src/components/EventFeed.tsx` — activate
- `web/src/pages/Dashboard.tsx` — import EventFeed
- `web/src/lib/api.ts` — add e2e_result to ChangeInfo

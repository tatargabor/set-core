# Design: gate-observability

## Current state

```
Gate pipeline (Python):
  dep_install → [silent success] → build → [silent success] → test → [silent success] → e2e → [silent success]
  Only failures log. No elapsed times. No summary.

Events emitted:
  VERIFY_GATE only on fail/redispatch. No GATE_START, no success events.

Web dashboard:
  GateBar: B T R S SC — no 'E' for e2e, no retry/redispatch status
  ChangeTimeline: Impl→Build→Test→Review→Smoke→Merge — no integration steps
  EventFeed: exists but unused
  Merge pipeline: invisible black box
```

## New state

```
Gate pipeline (Python):
  dep_install → INFO: "dep install PASSED (712ms)"
  build → INFO: "build PASSED (16351ms)"
  test → INFO: "test PASSED (1284ms)"
  e2e → INFO: "e2e PASSED (150739ms)"
  → INFO: "Integration gates for X: 4/4 passed in 169.1s"

Events:
  GATE_START {gate, change, phase}
  GATE_PASS {gate, change, elapsed_ms, phase}
  GATE_FAIL {gate, change, elapsed_ms, phase}  (existing VERIFY_GATE becomes this)
  MERGE_START {change}
  MERGE_COMPLETE {change, result}

State:
  e2e_result: "pass"|"fail"|"skip"   (separate from smoke_result)
  gate_e2e_ms: int                    (separate from gate_verify_ms)

Web:
  GateBar: B T R S E SC — 'E' for e2e with redispatch/retry styling
  EventFeed: live stream of GATE_* events
  ChangeTimeline: ...→Smoke→E2E→Integration→Merge with per-step status
```

## Implementation

### Python logging (merger.py)

For EACH gate step, wrap with timing:

```python
import time
_start = time.monotonic()
result = run_command(...)
_elapsed_ms = int((time.monotonic() - _start) * 1000)

if result.exit_code == 0:
    logger.info("Integration gate: %s PASSED for %s (%dms)", gate_name, change_name, _elapsed_ms)
    if event_bus:
        event_bus.emit("GATE_PASS", change=change_name, data={
            "gate": gate_name, "elapsed_ms": _elapsed_ms, "phase": "integration"})
```

At the end of all gates:
```python
logger.info("Integration gates for %s: %d/%d passed in %.1fs",
            change_name, passed_count, total_count, total_elapsed_ms / 1000)
```

### State field (state.py)

```python
e2e_result: Optional[str] = None
gate_e2e_ms: int = 0
```

### Web: GateBar.tsx

Add 'E' gate:
```tsx
{ name: 'e2e', status: e2e_result },  // before smoke or instead
```

Add `redispatch` status style:
```tsx
redispatch: 'bg-amber-900 text-amber-300',  // retry amber
```

### Web: EventFeed activation

In Dashboard.tsx, import EventFeed and render it in a new "Events" tab or as a sidebar alongside the log view.

### Web: ChangeTimeline merge steps

Add after Smoke phase:
```
E2E → Integration → Merge
```
Each with pass/fail/pending from the new state fields.

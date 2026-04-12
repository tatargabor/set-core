# Spec: gate-observability

## Capability

Full visibility into the gate/merge pipeline — every gate step logged with timing, events emitted for both success and failure, web dashboard shows E2E gate separately from smoke, merge pipeline visible as intermediate steps, and EventFeed activated for live event stream.

## Behavior

### Python logging
- Every gate step (dep install, build, test, e2e) logs INFO on success with elapsed_ms
- Summary line after all gates: "N/M passed in X.Xs"
- Failures continue to log ERROR/WARNING as before

### Events
- `GATE_START` emitted when each gate begins
- `GATE_PASS` emitted on success with elapsed_ms
- Existing `VERIFY_GATE` on failure kept for backwards compat
- `MERGE_START` / `MERGE_COMPLETE` for merge visibility

### State
- `e2e_result` field separate from `smoke_result`
- `gate_e2e_ms` field separate from `gate_verify_ms`

### Web dashboard
- GateBar shows 'E' icon for E2E alongside existing B T R S
- `redispatch` status renders as amber (retry indicator)
- EventFeed component activated in Dashboard
- ChangeTimeline shows E2E and merge as distinct phases

# Proposal: heartbeat-pre-emit

## Why

The monitor loop is single-threaded. Long-running operations (dispatch, merge, poll, replan) block heartbeat emission for minutes at a time. The sentinel's 180s stuck detection interprets this as a dead orchestrator and kills it — even though the process is healthy and working. In CraftBrew Run #3, this caused 3+ false-positive kills and required manual sentinel restarts.

## What Changes

- **Fix**: Emit a heartbeat event and touch the state file mtime **before** each long-running operation in the monitor loop, resetting the sentinel's idle timer
- **Fix**: Emit a heartbeat **after** long-running operations complete, so the sentinel sees continuous activity even for multi-minute operations
- **Modified**: Heartbeat frequency changes from "every 8th poll" (passive, gap-prone) to "around every blocking call" (active, gap-free)

## Capabilities

### New Capabilities
- `heartbeat-pre-emit` — Active heartbeat emission around long-running monitor operations to prevent false sentinel kills

### Modified Capabilities
_(none — no existing specs affected)_

## Impact

- **Files**: `lib/set_orch/engine.py` (monitor loop heartbeat placement)
- **Risk**: Very low — additive timing signals only, no behavioral changes
- **Testing**: Unit test for heartbeat helper + E2E validation that sentinel no longer false-kills during dispatch/merge

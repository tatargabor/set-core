## Why

The dispatcher's `dispatch_via_wt_loop()` silently accepts a `ralph_pid` of 0 when `loop-state.json` is missing the `terminal_pid` field, has a null value, or when JSON parsing fails. The broad exception handler swallows all errors, then proceeds to mark the change as `"running"` with `ralph_pid=0`. This creates an orphaned change that appears active but has no agent process — stuck indefinitely. The watchdog only detects this via timeout after 120+ seconds, but does not distinguish "invalid startup" from "agent crashed."

## What Changes

- **Validate PID after extraction**: If `terminal_pid` is 0/null/invalid after reading `loop-state.json`, fail the dispatch immediately instead of marking as "running"
- **Log exception details**: Replace the bare `pass` in the PID extraction try/except with `logger.error()` so failures are visible
- **Add watchdog fast-path**: Immediately escalate any change with `status="running"` and `ralph_pid` of 0/null — don't wait for timeout

## Capabilities

### New Capabilities

- `dispatch-pid-validation`: Validate that the launched agent process has a real PID before marking a change as "running". Fail fast on invalid PID.

### Modified Capabilities

<!-- No existing spec-level requirements change — this is a bug fix in the dispatch mechanism -->

## Impact

- **`lib/set_orch/dispatcher.py`**: PID validation logic in `dispatch_via_wt_loop()` (lines 1771-1782)
- **`lib/set_orch/watchdog.py`**: Fast-path null-PID detection in `watchdog_check()` (lines 134-173)
- **Risk**: Low — changes only add validation gates; existing working dispatches (positive PID) are unaffected

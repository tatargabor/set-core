## Why

The sentinel kills the orchestrator during checkpoint waits (stuck detection doesn't know about checkpoints), causing partial resets that lose coverage tracking. Requirements stay "planned" in coverage.json despite their changes being merged, and auto-replan can't detect the gap because `_check_completion` uses change statuses, not coverage.

## What Changes

- Fix sentinel stuck detection to be checkpoint-aware — don't kill the orchestrator while it's waiting for checkpoint approval
- Fix coverage tracking after sentinel restart — when the merge pipeline runs after a partial reset, coverage must be updated for all merged changes
- Fix completion check to validate coverage — `_check_completion` should detect when coverage.json has planned requirements for merged changes and trigger a coverage sync before declaring "done"

## Capabilities

### New Capabilities
- `checkpoint-aware-sentinel`: Sentinel respects checkpoint state during stuck detection — doesn't kill orchestrator waiting for user approval
- `coverage-consistency`: Coverage tracking remains consistent after sentinel restarts and partial resets

### Modified Capabilities
_none_

## Impact

- `bin/wt-sentinel` — stuck detection logic (checkpoint-aware timeout)
- `lib/wt_orch/engine.py` — `_check_completion()`, checkpoint state handling in monitor loop
- `lib/wt_orch/merger.py` — coverage sync on merge after restart
- `lib/wt_orch/digest.py` — coverage reconciliation helper

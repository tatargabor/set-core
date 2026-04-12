## Why

When a merge enters `merge-blocked` after FF retry exhaustion (3 attempts), the engine's recovery logic (`_recover_merge_blocked_safe`) transitions it back to `done` without resetting `ff_retry_count` or incrementing `merge_retry_count`. The monitor re-queues the `done` change, the merger sees `ff_retry_count >= 3`, skips integration gates, attempts FF merge (which fails again), and sets `merge-blocked` — creating a 15-second infinite loop that never terminates.

## What Changes

- **Recovery resets ff_retry_count**: When `_recover_merge_blocked_safe` recovers a change from `merge-blocked` → `done`, it resets `ff_retry_count` to 0 so the change gets a fresh set of merge attempts with full gate execution.
- **Recovery increments merge_retry_count**: Each recovery bumps `merge_retry_count` by 1, so the monitor's existing `merge_retry_count >= 3` guard (in `_poll_suspended_changes`) will eventually transition to `integration-failed` — a terminal state that stops the loop.

## Capabilities

### New Capabilities

- `merge-loop-fix`: Break the infinite merge-blocked → done → re-queue loop by resetting FF state on recovery and bounding total recovery attempts.

### Modified Capabilities

- `merge-retry-counter`: The recovery path now participates in the merge_retry_count budget, ensuring bounded retries across all merge paths.

## Impact

- **`lib/set_orch/engine.py`**: `_recover_merge_blocked_safe()` — add `ff_retry_count` reset and `merge_retry_count` increment on recovery.
- **No breaking changes**: The existing `merge_retry_count >= 3` terminal guard in the monitor is unchanged; recovery simply feeds into it.
- **If not fixed**: Any project where FF merge fails repeatedly (worktree rename, diverged history, transient errors) enters an infinite 15-second loop that wastes resources and blocks orchestration progress.

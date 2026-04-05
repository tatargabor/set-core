## Context

The merger's merge-blocked recovery creates an infinite loop when FF retries are exhausted. The recovery path (`_recover_merge_blocked_safe` in `engine.py`) transitions merge-blocked → done without resetting `ff_retry_count` or incrementing `merge_retry_count`. This means:
1. The change re-enters the merge queue with `ff_retry_count >= 3`
2. The merger skips integration gates and immediately hits the FF retry limit → merge-blocked
3. Recovery fires again → done → re-queue → loop every ~15 seconds

## Goals / Non-Goals

**Goals:**
- Break the infinite merge loop with a minimal, correct fix
- Ensure bounded retries: the loop terminates after a finite number of recovery attempts

**Non-Goals:**
- Changing the FF merge command construction (worktree lookup already fixed in `cff322956`)
- Modifying retry limits or adding new configuration

## Decisions

**Decision: Reset ff_retry_count on recovery, increment merge_retry_count**

When `_recover_merge_blocked_safe` transitions a change from merge-blocked → done:
1. Reset `ff_retry_count` to 0 — gives the change a fresh set of FF retries with full gate execution
2. Increment `merge_retry_count` by 1 — feeds into the monitor's existing `>= 3` terminal guard

*Alternative considered:* Transition directly to `integration-failed` when `ff_retry_count >= 3`. Rejected because it would prevent recovery from transient issues (e.g., the worktree lookup bug that's now fixed). The bounded-retry approach is more resilient.

*Alternative considered:* Check `ff_retry_count` in recovery and skip recovery if exhausted. Rejected because this would make merge-blocked permanent with no path to resolution, even after the root cause is fixed.

## Risks / Trade-offs

- [Risk] Recovery resets ff_retry_count, allowing 3 more FF attempts per recovery cycle → up to 9 total FF attempts before terminal failure. → Acceptable: each cycle runs full integration gates, providing diagnostic value.

## Migration Plan

No migration needed. The fix is backwards-compatible — existing state files with `ff_retry_count` and `merge_retry_count` fields work as-is.

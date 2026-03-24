# Design: Craftbrew Run #10 Fixes

## D1: Duplicate Dispatch Guard

**Decision:** Add atomic status check in `dispatch_change()` before worktree creation.

Before creating the worktree, re-read state and verify the change is still "pending". Use `locked_state` context manager for atomic read+write:

```python
with locked_state(state_path) as st:
    ch = _find_change(st, change_name)
    if ch.status != "pending":
        logger.info("Change %s already dispatched (status=%s), skipping", change_name, ch.status)
        return False
    ch.status = "dispatched"  # Mark immediately to prevent race
```

This prevents the race where two monitor cycles both see "pending" and dispatch.

## D2: Merge Retry Counter

**Decision:** Track `merge_retry_count` on change, max 3 retries → `integration-failed` status.

In `retry_merge_queue()`, before re-adding to queue:
- Read `merge_retry_count` from change extras
- If >= 3, set status to `integration-failed` (terminal)
- Otherwise increment and re-add to queue

The `integration-failed` status is already treated as terminal by the engine.

## D3: Stall Detection Reorder

**Decision:** In `lib/loop/engine.sh`, check done BEFORE checking stall.

Current order: commit check → stall detect → done check
New order: done check → commit check → stall detect

If all tasks are `[x]`, skip stall detection entirely and mark done.

## D4: Vitest Planning Rule

**Decision:** Add explicit rule to `planning_rules.txt` requiring test script in package.json for infrastructure changes.

Text: "The infrastructure/foundation change MUST ensure package.json includes a `test` script (e.g., `vitest run`) and vitest in devDependencies. Do NOT defer test runner setup to later changes."

## D5: Dedicated Pre-Build Hook

**Decision:** Add `integration_pre_build(wt_path)` method to `ProjectType` ABC. Web module implements it with `prisma db push --skip-generate` only (no seed).

The current `e2e_pre_gate` runs seed which is wasteful for build. The new hook does minimal DB schema sync.

Merger calls `integration_pre_build()` instead of `e2e_pre_gate()` before the build gate.

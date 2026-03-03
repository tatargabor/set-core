## Context

The orchestrator's cleanup trap sets change status to `"stopped"` when interrupted. On restart, the resume path calls `dispatch_ready_changes()` which only handles `"pending"` changes, and the monitor loop only polls `"running"` and `"verifying"`. The `"stopped"` status is a dead zone.

## Goals / Non-Goals

**Goals:**
- Auto-resume `stopped` changes on orchestrator restart
- Verify worktree still exists before resuming (it may have been manually removed)
- Log clearly what's happening for observability

**Non-Goals:**
- Changing the cleanup trap behavior (it correctly marks changes as stopped)
- Adding new retry logic (existing stall_count/resume_change handles that)

## Decisions

1. **Resume at restart, not in poll loop**: The fix goes in the resume path of `cmd_start()` (line ~2136-2139), before `dispatch_ready_changes`. This is the natural place — "orchestrator restarting, pick up where we left off." The poll loop filter stays unchanged (running|verifying).

2. **Use existing `resume_change()`**: The `resume_change()` function already handles re-dispatching to an existing worktree. We just need to call it for each stopped change, which also sets status back to `"running"`.

3. **Worktree check before resume**: If the worktree was manually removed while stopped, skip the resume and set status to `"pending"` so it gets re-dispatched fresh.

4. **No stall_count increment**: This is not a stall — it's a normal restart. Don't increment stall_count.

## Risks / Trade-offs

- **Race with dispatch**: `resume_change` sets status to `"running"`, so `dispatch_ready_changes` won't double-dispatch. No race.
- **Dead worktree**: If worktree exists but is corrupted, `resume_change` may fail. Existing stall handling catches this on the next poll cycle.

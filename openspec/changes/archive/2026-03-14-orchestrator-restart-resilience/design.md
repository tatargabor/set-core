## Context

When the orchestrator process dies (crash, SIGKILL, manual stop) and restarts, `cmd_start()` in `dispatcher.sh` detects the crashed state (line 333-354): it checks for live Ralph PIDs, and if none found, sets orchestrator status to "stopped" and enters the resume path.

The resume path (line 367-443) calls:
1. `recover_orphaned_changes()` — resets running changes **without a worktree** to pending
2. `retry_merge_queue()` — retries merge-blocked changes
3. `resume_stopped_changes()` — redispatches changes with status "stopped"
4. `dispatch_ready_changes()` — dispatches pending changes

**The gap**: `recover_orphaned_changes()` skips changes whose worktree directory still exists (line 342), even if the agent process is dead. These changes remain "running" — `resume_stopped_changes()` ignores them (only handles "stopped"), so they sit idle until the monitor's stall detection kicks in (5+ minutes).

Additionally, `phase_audit_results` and `phase_e2e_results` from the crashed execution persist across restarts via the state file. The replan path in `planner.sh` (line 907-928) intentionally preserves these for cycle-to-cycle continuity, but on a fresh restart they are stale.

## Goals / Non-Goals

**Goals:**
- Eliminate the 5+ minute stall window after orchestrator restart by reconciling per-change status against live processes
- Clear stale audit/e2e results on restart while preserving them during replan
- Emit events for observability when reconciliation occurs

**Non-Goals:**
- Changing the existing `recover_orphaned_changes()` behavior for worktree-less changes (that works correctly)
- Modifying the replan carry-forward logic (that is correct for its use case)
- Adding auto-restart capability to the orchestrator itself

## Decisions

### Decision 1: Extend `recover_orphaned_changes()` with PID liveness check for worktree-present changes

**Choice**: Add a second pass in `recover_orphaned_changes()` that handles changes with existing worktrees but dead PIDs. These get reset to "stopped" (not "pending") because the worktree contains partial work that `resume_stopped_changes()` can leverage.

**Alternative considered**: Create a separate `reconcile_running_changes()` function. Rejected because the logic is a natural extension of orphan recovery — both deal with "status says running but nothing is actually running."

**Rationale**: Setting to "stopped" rather than "pending" is important: the worktree may contain committed work. `resume_stopped_changes()` already handles the resume-from-worktree flow correctly.

### Decision 2: Clear audit/e2e results in the bash resume path, not in Python

**Choice**: In `dispatcher.sh` cmd_start() resume path (after line 370), clear `phase_audit_results` and `phase_e2e_results` from state. This is distinct from the replan path in `planner.sh` which preserves them.

**Alternative considered**: Add a "restart_count" or "execution_id" to distinguish restart from replan. Rejected as over-engineering — simply clearing in the right code path is sufficient.

**Rationale**: The resume path in dispatcher.sh handles crash recovery; the replan path in planner.sh handles cycle progression. They are separate code paths, so the fix naturally goes in the right place.

### Decision 3: Emit CHANGE_RECONCILED event (reuse existing event pattern)

**Choice**: Emit a `CHANGE_RECONCILED` event with `reason: "dead_pid_live_worktree"` for each change reset during reconciliation. This is distinct from the existing `CHANGE_RECOVERED` event (which covers the no-worktree case).

**Rationale**: Different event names allow the dashboard/monitor to distinguish between true orphans (worktree gone) and stale-running (worktree present, agent dead). Both are logged for post-mortem analysis.

## Risks / Trade-offs

- **[Risk] PID race condition**: Between checking PID liveness and resetting status, a new process could reuse the PID. → Mitigation: `check_pid()` already validates the process command matches "wt-loop", making false positives extremely unlikely.
- **[Risk] Clearing audit results loses diagnostic data**: Stale audit results from a crashed run are deleted. → Mitigation: Audit debug logs (`audit-cycle-N.log`) persist in `wt/orchestration/` regardless. The state field is for dashboard display, not archival.
- **[Trade-off] "stopped" vs "pending" for worktree-present changes**: Using "stopped" means the change will be resumed (keeping worktree work), but if the worktree is corrupted, resume may fail. → Acceptable: the existing resume flow already handles corrupted worktrees by falling back to redispatch.

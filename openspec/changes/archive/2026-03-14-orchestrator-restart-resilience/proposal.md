## Why

When the orchestrator process restarts (crash, manual stop, sentinel restart), two inconsistencies arise: (1) changes with status "running" whose agent processes are dead remain as orphaned "running" entries — the resume path only resets the orchestrator-level status to "stopped" but does not reconcile per-change statuses with actual process liveness, causing 5+ minute stalls until the monitor eventually detects inactivity; (2) `phase_audit_results` from the previous failed execution persist in the state file across restarts, displaying stale/misleading audit data in the dashboard.

## What Changes

- Add per-change PID liveness reconciliation during the orchestrator resume path: changes with status "running"/"verifying" whose `ralph_pid` is dead get reset to "stopped" so `resume_stopped_changes()` picks them up immediately
- Clear `phase_audit_results` and `phase_e2e_results` on orchestrator restart (fresh execution context), while preserving them during replan cycles (same execution context)
- Emit `CHANGE_RECONCILED` events when orphaned running changes are detected and reset

## Capabilities

### New Capabilities
- `restart-state-reconciliation`: Per-change process liveness check and status reconciliation during orchestrator resume, plus stale audit/e2e result cleanup

### Modified Capabilities
- `dispatch-recovery`: Extends the resume path to reconcile individual change statuses against live processes before dispatching

## Impact

- `lib/orchestration/dispatcher.sh` — resume path in `cmd_start()` (lines ~330-440)
- `lib/orchestration/dispatcher.sh` — `cmd_resume()` function
- `wt_orch/dispatcher.py` — `resume_stopped_changes()` Python counterpart
- `lib/orchestration/planner.sh` — audit results carry-forward logic (lines ~907-928) needs awareness of restart vs replan distinction
- Orchestration events JSONL — new `CHANGE_RECONCILED` event type
- Web dashboard — stale audit results will no longer appear after restart

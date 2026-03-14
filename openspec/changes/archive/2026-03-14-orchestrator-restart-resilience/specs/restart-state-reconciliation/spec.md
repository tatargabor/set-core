## ADDED Requirements

### Requirement: Reconcile per-change status against live processes on resume
The orchestrator SHALL check each "running" or "verifying" change for process liveness during the resume path, and reset changes with dead agent processes to "stopped" so they are immediately eligible for re-dispatch.

#### Scenario: Worktree exists but PID is dead
- **WHEN** the orchestrator resumes and a change has status "running" or "verifying"
- **AND** the change's worktree directory exists
- **AND** the change's `ralph_pid` is not alive or does not match "wt-loop"
- **THEN** the change status SHALL be set to "stopped"
- **AND** the change's `ralph_pid` SHALL be cleared
- **AND** a `CHANGE_RECONCILED` event SHALL be emitted with `reason: "dead_pid_live_worktree"`

#### Scenario: Worktree exists and PID is alive
- **WHEN** the orchestrator resumes and a change has status "running" or "verifying"
- **AND** the change's worktree directory exists
- **AND** the change's `ralph_pid` is alive and matches "wt-loop"
- **THEN** the change SHALL be left unchanged (agent is still working)

#### Scenario: No PID recorded
- **WHEN** the orchestrator resumes and a change has status "running" or "verifying"
- **AND** the change's worktree directory exists
- **AND** the change has no `ralph_pid` (null or 0)
- **THEN** the change status SHALL be set to "stopped"
- **AND** a `CHANGE_RECONCILED` event SHALL be emitted with `reason: "no_pid_live_worktree"`

#### Scenario: Reconciliation logging
- **WHEN** one or more changes are reconciled during resume
- **THEN** the orchestrator SHALL log the count and names of reconciled changes
- **AND** each reconciled change SHALL be logged individually with its previous status

### Requirement: Clear stale audit and E2E results on orchestrator restart
The orchestrator SHALL clear `phase_audit_results` and `phase_e2e_results` from state when resuming from a crashed or stopped state, since these results belong to the previous execution context.

#### Scenario: Resume clears stale results
- **WHEN** the orchestrator enters the resume path (status was "running" with no live PIDs, or "stopped", or "time_limit")
- **THEN** `phase_audit_results` SHALL be set to an empty array `[]`
- **AND** `phase_e2e_results` SHALL be set to an empty array `[]`
- **AND** a log entry SHALL note that stale results were cleared

#### Scenario: Replan preserves results
- **WHEN** the orchestrator enters a replan cycle (via `auto_replan_cycle()`)
- **THEN** `phase_audit_results` SHALL be preserved (existing behavior, no change)
- **AND** `phase_e2e_results` SHALL be preserved (existing behavior, no change)

## MODIFIED Requirements

### Requirement: Recover orphaned changes
The system SHALL detect changes with status running/verifying/stalled that have no worktree directory AND no live Ralph PID, and reset them to "pending" with cleared worktree_path, ralph_pid, and verify_retry_count. A CHANGE_RECOVERED event SHALL be emitted. Additionally, changes with an existing worktree but a dead or missing Ralph PID SHALL be reset to "stopped" with cleared ralph_pid, and a CHANGE_RECONCILED event SHALL be emitted.

#### Scenario: Orphaned change (no worktree, dead PID)
- **WHEN** a running change has no worktree directory and its ralph_pid is not alive
- **THEN** status is reset to "pending", fields cleared, CHANGE_RECOVERED event emitted

#### Scenario: Change with live PID but missing worktree
- **WHEN** a running change has a live ralph_pid matching "wt-loop"
- **THEN** the change is skipped (process is running somewhere)

#### Scenario: Change with existing worktree but dead PID
- **WHEN** a running/verifying change's worktree directory exists
- **AND** the change's ralph_pid is not alive or does not match "wt-loop"
- **THEN** status SHALL be reset to "stopped" (preserving worktree for resume)
- **AND** ralph_pid SHALL be cleared
- **AND** a CHANGE_RECONCILED event SHALL be emitted with reason "dead_pid_live_worktree"

#### Scenario: Change with existing worktree and live PID
- **WHEN** a running change's worktree directory exists
- **AND** the change's ralph_pid is alive and matches "wt-loop"
- **THEN** the change is skipped (agent is still working)

#### Scenario: Change with existing worktree and no PID
- **WHEN** a running/verifying change's worktree directory exists
- **AND** the change has no ralph_pid (null or 0)
- **THEN** status SHALL be reset to "stopped"
- **AND** a CHANGE_RECONCILED event SHALL be emitted with reason "no_pid_live_worktree"

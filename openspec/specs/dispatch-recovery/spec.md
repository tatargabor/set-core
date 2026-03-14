## ADDED Requirements

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

### Requirement: Redispatch stuck changes
The system SHALL kill the Ralph PID (safe-kill), salvage partial work (diff + file list), build retry_context with failure metadata, increment redispatch_count, clean up old worktree (git worktree remove + branch delete), reset watchdog state, and set status to "pending" for natural re-dispatch.

#### Scenario: Redispatch with clean worktree removal
- **WHEN** redispatch is triggered for a stuck change
- **THEN** Ralph is killed, worktree removed, retry_context built, status set to "pending"

#### Scenario: Redispatch worktree removal fallback
- **WHEN** `git worktree remove --force` fails
- **THEN** the worktree directory is removed via `rm -rf` fallback

#### Scenario: Redispatch watchdog reset
- **WHEN** a change is redispatched
- **THEN** watchdog sub-object is reset (activity epoch, action_hash_ring cleared, escalation reset to 0)

### Requirement: Retry failed builds
The system SHALL give build-failed changes a chance to self-repair before triggering full replan. Changes with status "failed" and build_result "fail" SHALL be retried up to max_retries times. Retry context includes build output and original scope.

#### Scenario: Build retry within limit
- **WHEN** a failed build has gate_retry_count < max_retries
- **THEN** retry_context is set with build output, status reset to "pending", and resume_change is called

#### Scenario: Build retry exhausted
- **WHEN** gate_retry_count >= max_retries
- **THEN** the change is skipped (retries exhausted, awaits replan)

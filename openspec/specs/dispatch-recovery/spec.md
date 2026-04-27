# dispatch-recovery Specification

## Purpose

Recover orphaned, stuck, or build-failed changes back to a dispatchable state. Detects mismatches between recorded change status and live worktree/Ralph PID state, salvages partial work on redispatch, and retries failed builds within a bounded budget before escalating to replan.
## Requirements
### Requirement: Recover orphaned changes
The system SHALL detect changes with status running/verifying/stalled that have no worktree directory AND no live Ralph PID, and reset them to "pending" with cleared worktree_path, ralph_pid, and verify_retry_count. A CHANGE_RECOVERED event SHALL be emitted. Additionally, changes with an existing worktree but a dead or missing Ralph PID SHALL be reset to "stopped" with cleared ralph_pid, and a CHANGE_RECONCILED event SHALL be emitted.

#### Scenario: Orphaned change (no worktree, dead PID)
- **WHEN** a running change has no worktree directory and its ralph_pid is not alive
- **THEN** status is reset to "pending", fields cleared, CHANGE_RECOVERED event emitted

#### Scenario: Change with live PID but missing worktree
- **WHEN** a running change has a live ralph_pid matching "set-loop"
- **THEN** the change is skipped (process is running somewhere)

#### Scenario: Change with existing worktree but dead PID
- **WHEN** a running/verifying change's worktree directory exists
- **AND** the change's ralph_pid is not alive or does not match "set-loop"
- **THEN** status SHALL be reset to "stopped" (preserving worktree for resume)
- **AND** ralph_pid SHALL be cleared
- **AND** a CHANGE_RECONCILED event SHALL be emitted with reason "dead_pid_live_worktree"

#### Scenario: Change with existing worktree and live PID
- **WHEN** a running change's worktree directory exists
- **AND** the change's ralph_pid is alive and matches "set-loop"
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

### Requirement: reset_change_to_pending does not silently leave on-disk artifacts

Callers of `reset_change_to_pending` SHALL ensure that a change's on-disk worktree directory and `change/<name>` branch are removed either before or after the in-memory reset. The reset helper itself is explicitly state-only; the caller is responsible for artifact cleanup via `cleanup_change_artifacts` or via a bespoke plan-driven path (as in `set-recovery`).

#### Scenario: Circuit-breaker retry pairs cleanup with reset
- **WHEN** `IssueManager._retry_parent_after_resolved` resets a parent change
- **THEN** `cleanup_change_artifacts(parent_name, project_path)` SHALL run before `reset_change_to_pending`
- **AND** the removal result SHALL be audit-logged

#### Scenario: Recovery CLI retains its plan-driven worktree/branch removal
- **WHEN** `set-recovery` executes its rollback plan
- **THEN** the existing inline loops that iterate `plan.worktrees_to_remove` and `plan.branches_to_delete` SHALL continue to perform removal with their own idempotency guards
- **AND** the recovery path SHALL NOT introduce a redundant second cleanup pass via `cleanup_change_artifacts`
- **AND** the helper remains available for ad-hoc operator use but is not invoked from the plan executor

#### Scenario: reset_change_to_pending documents the contract
- **WHEN** a developer reads `reset_change_to_pending`'s docstring
- **THEN** the docstring SHALL explicitly warn that the function does NOT remove on-disk worktree/branch artifacts
- **AND** it SHALL reference `cleanup_change_artifacts` (or the recovery plan path) as the required companion when a caller wants a fresh re-dispatch

#### Scenario: reset_change_to_pending clears the merge-stall counter
- **WHEN** `reset_change_to_pending(ch)` runs
- **THEN** `ch.extras["merge_stall_attempts"]` SHALL be cleared (removed or set to 0) alongside the other gate-result extras
- **AND** a re-dispatched change SHALL begin with a fresh stall counter

### Requirement: Recovery plan execution tolerates already-removed artifacts

The recovery plan executor SHALL tolerate an artifact already being gone (e.g., because another component removed it during the same recovery pass) and SHALL NOT fail the whole rollback on such a benign mismatch.

#### Scenario: Worktree already removed
- **WHEN** the recovery executor tries to remove a worktree listed in the plan
- **AND** the worktree directory is already absent
- **THEN** the executor SHALL log at INFO and continue to the next step
- **AND** SHALL NOT raise or mark the rollback as failed

#### Scenario: Branch already deleted
- **WHEN** the recovery executor tries to delete a branch listed in the plan
- **AND** the branch is already absent
- **THEN** the executor SHALL log at INFO and continue
- **AND** SHALL NOT raise

### Requirement: Rollback preview warns about active issues outside rollback scope

`recovery.render_preview` SHALL append a "Warnings" section listing any active issue (state in INVESTIGATING, DIAGNOSED, AWAITING_APPROVAL, FIXING) whose `affected_change` is NOT in the rollback's `rollback_changes` set. The rollback still proceeds; the warning is advisory so operators can manually close or dismiss orphaned issues before the rollback executes.

#### Scenario: Active issue inside rollback scope — not listed
- **WHEN** render_preview runs for a plan that rolls back change "foo"
- **AND** an active issue's `affected_change` equals "foo"
- **THEN** the warning section SHALL NOT mention this issue (it will be cleaned up by rollback)

#### Scenario: Active issue outside rollback scope — listed
- **WHEN** render_preview runs for a plan that rolls back change "foo"
- **AND** an active issue's `affected_change` is "bar" (NOT in rollback_changes)
- **THEN** the warning section SHALL include one line per such issue: id, state, affected_change, and fix-iss child name if any

#### Scenario: No active outside-scope issues — section omitted
- **WHEN** no active issues reference changes outside the rollback scope
- **THEN** the warning section SHALL NOT appear in the preview output

#### Scenario: Terminal-state issues ignored
- **WHEN** an issue's state is RESOLVED, DISMISSED, MUTED, CANCELLED, SKIPPED, or FAILED
- **THEN** it SHALL NOT be listed in the warning section regardless of scope

#### Scenario: Registry unreadable — graceful degradation
- **WHEN** the issue registry file is missing or malformed
- **THEN** `render_preview` SHALL NOT raise
- **AND** SHALL proceed without the warning section (a DEBUG log MAY note the registry access failure)


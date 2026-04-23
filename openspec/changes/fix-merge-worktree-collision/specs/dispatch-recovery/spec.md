## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Clean orphaned worktrees on startup

The orchestrator SHALL detect and remove worktrees that exist on disk but have no corresponding change entry in the orchestration state, or whose change is already merged/done.

`cleanup_orphans()` SHALL accept a `force_dirty: bool = False` parameter. When `force_dirty=True` (used only by `engine.auto_replan_cycle()` during divergent-plan reconciliation), dirty worktrees whose change name is NOT in the new plan SHALL be stashed and archived instead of skipped. When `force_dirty=False` (default startup cleanup), the conservative "skip dirty" behavior is retained.

#### Scenario: Worktree exists but no state entry
- **WHEN** the orchestrator starts
- **AND** a worktree directory `<project>-wt-<name>` exists
- **AND** no change named `<name>` exists in orchestration-state.json
- **THEN** the worktree is removed via `git worktree remove --force`
- **AND** the orphaned branch `change/<name>` is deleted
- **AND** a log message is emitted: "Removed orphaned worktree: <name>"

#### Scenario: Worktree exists for merged change
- **WHEN** a change has status `merged` or `done`
- **AND** its worktree directory still exists on disk
- **AND** the worktree has no uncommitted changes (git status clean)
- **THEN** the worktree is removed
- **AND** a log message is emitted

#### Scenario: Worktree has uncommitted changes (default startup cleanup)
- **WHEN** a worktree exists for a merged/done change
- **AND** `cleanup_orphans()` was called with `force_dirty=False` (default)
- **AND** `git status --porcelain` in the worktree returns non-empty output
- **THEN** the worktree is NOT removed
- **AND** a warning is logged: "Skipping dirty worktree: <name> (has uncommitted changes)"

#### Scenario: Worktree has uncommitted changes during divergent-plan reconciliation
- **WHEN** `cleanup_orphans()` was called with `force_dirty=True` by `auto_replan_cycle()`
- **AND** the worktree's change name is NOT in the new plan
- **AND** `git status --porcelain` returns non-empty output
- **THEN** the function SHALL run `git stash push -u -m "auto-stash: divergent-replan <ts>"` inside the worktree
- **AND** archive the worktree path to `<worktree>.removed.<epoch>`
- **AND** remove the worktree via `git worktree remove --force`
- **AND** log the stash ref for recovery at INFO level

#### Scenario: Worktree belongs to active change
- **WHEN** a worktree exists for a change with status `running`, `pending`, or `dispatched`
- **THEN** the worktree is NOT touched regardless of `force_dirty`
- **AND** no log message is emitted

### Requirement: Conservative safety rules

The cleanup SHALL follow conservative rules to avoid destroying useful state. The `force_dirty` escape hatch is narrowly scoped: it SHALL only apply to worktrees whose change name is absent from the currently active plan.

#### Scenario: Never kill processes
- **WHEN** an orphaned worktree has a running process in its directory
- **THEN** the worktree is NOT removed regardless of `force_dirty`
- **AND** a warning is logged: "Skipping worktree <name>: process running in directory"

#### Scenario: Stash failure falls back to rescue branch
- **WHEN** `force_dirty=True` and `git stash push -u` fails inside a dirty worktree (e.g. no HEAD, detached state, pre-commit hook refuses)
- **THEN** the function SHALL create a rescue branch `wip/<name>-<epoch>` in the worktree's own repo
- **AND** commit the WIP with `git add -A && git commit -m "auto-commit: divergent-replan WIP <ts>" --no-verify`
- **AND** log a WARNING with the rescue branch name and the owning repo path
- **AND** proceed with archive + remove

#### Scenario: Log all actions
- **WHEN** any cleanup action is taken (worktree removal, PID clear, step fix, stash, rescue commit)
- **THEN** the action is logged at INFO level with the change name and details
- **AND** a summary line at the end: "Orphan cleanup: N worktrees removed, M PIDs cleared, K steps fixed, P dirty forced"

#### Scenario: No cleanup needed
- **WHEN** the orchestrator starts
- **AND** no orphaned resources are detected
- **THEN** no state modifications are made
- **AND** a debug message is logged: "Orphan cleanup: nothing to clean"

## ADDED Requirements

### Requirement: Orphan cleanup returns structured summary
The function SHALL return a dict with fields `worktrees_removed: int`, `dirty_skipped: int`, `dirty_forced: int`, `pids_cleared: int`, `steps_fixed: int`, `artifacts_collected: int`, `merge_queue_entries_restored: int`, `issues_released: int`. Callers (including the engine and the supervisor) SHALL consume this dict rather than parsing log lines.

#### Scenario: Summary reflects all action counts
- **WHEN** `cleanup_orphans(force_dirty=True)` archives 3 dirty worktrees plus 2 clean orphans and clears 1 stale PID
- **THEN** the returned dict SHALL equal `{"worktrees_removed": 5, "dirty_skipped": 0, "dirty_forced": 3, "pids_cleared": 1, "steps_fixed": 0, "artifacts_collected": 0, "merge_queue_entries_restored": 0, "issues_released": 0}`

## ADDED Requirements

### Requirement: Divergent-plan state reconciliation
When `auto_replan_cycle()` produces a new plan whose change-name set diverges from the prior plan's change-name set, the engine SHALL reconcile residual state so the new plan is not tangled with artifacts from the prior plan.

Divergence is defined as: `(old_plan_names ∪ new_plan_names) \ (old_plan_names ∩ new_plan_names) ≠ ∅`.

Reconciliation SHALL run AFTER `planner.collect_replan_context()` has captured its snapshot of `completed_names` and `merged_names`, so stale artifacts removed during reconciliation do NOT enter the replan prompt.

#### Scenario: New plan introduces entirely new change names
- **WHEN** the prior plan had change set `{A, B, C, D, E, F, G}` and the new plan has `{P, Q, R, S, T, U}` (zero intersection)
- **THEN** reconciliation SHALL archive every worktree whose branch name is not in the new plan
- **AND** SHALL delete every `change/<name>` branch not in the new plan
- **AND** SHALL remove every `openspec/changes/<name>/` dir whose `<name>` is neither in the new plan nor in `state-archive.jsonl`

#### Scenario: Partial overlap preserves shared names
- **WHEN** the prior plan had `{A, B, C}` and the new plan has `{B, C, D}`
- **THEN** reconciliation SHALL NOT touch worktrees, branches, or `openspec/changes/` dirs for `B` or `C`
- **AND** SHALL clean up only `A` artifacts

#### Scenario: Replan context captured before reconciliation
- **WHEN** `auto_replan_cycle()` runs
- **THEN** the sequence SHALL be: (1) `collect_replan_context()` captures a snapshot of `completed_names`/`merged_names`, (2) generate plan via Claude, (3) validate plan, (4) reconcile-on-divergence, (5) initialize new state from the plan
- **AND** reconciliation SHALL NOT run until after plan validation so a failed plan does not destroy state
- **AND** changes archived by reconciliation SHALL NOT retroactively appear in the replan prompt's `completed_names` (the snapshot is immutable)

### Requirement: Reconciler writes a cleanup manifest and honors dry-run
Before any branch-delete or `openspec/changes/<name>/` dir-remove operation during divergent-plan reconciliation, the engine SHALL write a manifest file `orchestration-cleanup-<epoch>.log` in the project root listing every branch and dir path scheduled for removal. The manifest SHALL include the cleanup operation, absolute path, and rationale (`not in new plan`, `not in state-archive.jsonl`).

The directive `divergent_plan_dir_cleanup` SHALL support values `enabled` (default, destructive operations execute) and `dry-run` (manifest is written but no deletes occur). This provides a single-toggle rollback for the irreversible parts of reconciliation.

#### Scenario: Manifest written before destructive action
- **WHEN** reconciliation plans to delete branches `{A, B}` and dirs `openspec/changes/{X, Y}/`
- **THEN** a file `orchestration-cleanup-<epoch>.log` SHALL be written FIRST, listing each path with its operation and rationale
- **AND** only after the manifest write succeeds SHALL the destructive operations proceed

#### Scenario: dry-run mode preserves state
- **WHEN** the directive `divergent_plan_dir_cleanup=dry-run` is set
- **THEN** the manifest SHALL still be written
- **AND** no `git branch -D` or `rm -rf openspec/changes/<name>/` SHALL be executed
- **AND** the log line `Cleanup dry-run: would have removed N branches, M dirs — see manifest` SHALL be emitted at INFO

### Requirement: Dirty worktrees are force-cleaned on divergence
During divergent-plan reconciliation, worktrees with uncommitted changes SHALL NOT be skipped. The engine SHALL stash uncommitted work (`git stash push -u -m "auto-stash: divergent-replan reconciliation <timestamp>"`) before archiving the worktree, so the merge/WIP is preserved on the ref-log but the worktree can be removed.

This changes prior behavior where `orphan_cleanup` logged `"Skipping dirty worktree: <name> (has uncommitted changes)"` and left the worktree in place.

#### Scenario: Dirty worktree from prior plan
- **WHEN** reconciliation encounters a worktree `craftbrew-run-20260418-1719-wt-foundation-setup` with `git status --porcelain` showing uncommitted changes
- **AND** `foundation-setup` is not in the new plan
- **THEN** the engine SHALL `git stash push -u` inside that worktree first
- **AND** SHALL archive the worktree path to `<name>.removed.<epoch>` (existing archive convention)
- **AND** SHALL log the stash ref and archive path at INFO level for recovery

### Requirement: Supervisor rapid_crashes reset on clean plan completion
When every change in the current plan reaches a terminal status (`done`, `merged`, `skipped`, or `failed:user_accepted`) and no new replan is triggered, the supervisor SHALL reset `SupervisorStatus.rapid_crashes` to 0 and persist. This prevents stale crash counters from surviving across healthy plan cycles.

#### Scenario: rapid_crashes carries across plan cycles
- **WHEN** a plan completes with all changes terminal and `rapid_crashes > 0` on the supervisor status
- **THEN** the supervisor SHALL write `rapid_crashes = 0` to `supervisor-status.json`
- **AND** log `Supervisor rapid_crashes reset on plan completion (was: N)` at INFO

#### Scenario: rapid_crashes persists across mid-plan restarts
- **WHEN** the supervisor restarts while any change is still `running` or `stalled`
- **THEN** `rapid_crashes` SHALL be preserved (current behavior retained)

# change-artifact-cleanup Specification

## Purpose

Provide a single, idempotent helper for removing a change's on-disk artifacts (worktree directory + `change/<name>` git branch) so reset, recovery, and archive paths can call one contract without each reimplementing safe-removal logic.

### In scope
- Idempotent removal of a change's worktree directory and its `change/<name>` git branch
- Safe handling of already-removed artifacts (no error on missing worktree or missing branch)
- Single callable contract usable from any reset/recovery path
- Logging of what was removed and what was already absent

### Out of scope
- Deleting per-change journals, activity-detail JSONL files, or archived logs — retained for forensics
- Mutating `state.json` — caller is responsible for state changes
- Removing openspec change directories (`openspec/changes/<name>/`) — handled separately by archive/rollback flows
- Cross-lineage awareness — operates on the live lineage only

## Requirements

### Requirement: Shared cleanup helper for change artifacts

The system SHALL provide a single function `cleanup_change_artifacts(change_name, project_path)` in `lib/set_orch/change_cleanup.py` that removes a change's worktree directory and `change/<name>` git branch, tolerant of missing artifacts.

#### Scenario: Worktree and branch both present
- **WHEN** `cleanup_change_artifacts("foo", "/repos/acme")` runs
- **AND** `/repos/acme-wt-foo` is a registered git worktree
- **AND** `change/foo` is a local branch
- **THEN** `git worktree remove --force /repos/acme-wt-foo` SHALL run
- **AND** `git worktree prune` SHALL run
- **AND** `git branch -D change/foo` SHALL run
- **AND** each successful removal SHALL be logged at INFO

#### Scenario: Worktree already removed on disk
- **WHEN** `cleanup_change_artifacts("foo", "/repos/acme")` runs
- **AND** `/repos/acme-wt-foo` does not exist
- **THEN** `git worktree remove` SHALL be skipped
- **AND** `git worktree prune` SHALL still run
- **AND** the function SHALL NOT raise

#### Scenario: Worktree exists but is unregistered
- **WHEN** `cleanup_change_artifacts("foo", "/repos/acme")` runs
- **AND** `/repos/acme-wt-foo` exists on disk but is not listed by `git worktree list --porcelain`
- **THEN** the directory SHALL be removed via `rm -rf` fallback
- **AND** a WARN log SHALL record the unregistered-worktree condition

#### Scenario: Branch already deleted
- **WHEN** `cleanup_change_artifacts("foo", "/repos/acme")` runs
- **AND** `change/foo` does not exist as a local branch
- **THEN** `git branch -D` SHALL be skipped (or its non-zero exit ignored)
- **AND** the function SHALL NOT raise

#### Scenario: Repeated invocation is idempotent
- **WHEN** `cleanup_change_artifacts("foo", project_path)` is called twice in succession
- **THEN** the second call SHALL succeed as a no-op
- **AND** the final return SHALL indicate that nothing remained to clean

#### Scenario: Alternative naming conventions recognised
- **WHEN** a worktree exists at `/repos/acme-foo` (Python-convention, no `-wt-` infix)
- **AND** `cleanup_change_artifacts("foo", "/repos/acme")` runs
- **THEN** both `/repos/acme-wt-foo` and `/repos/acme-foo` paths SHALL be considered for removal
- **AND** any existing variant SHALL be removed

### Requirement: Cleanup returns a structured result

The helper SHALL return a value indicating which artifacts were present-and-removed versus already-absent, so callers can log or report the outcome.

#### Scenario: Structured return value
- **WHEN** `cleanup_change_artifacts("foo", project_path)` completes
- **THEN** it SHALL return an object with `worktree_removed: bool`, `branch_removed: bool`, and a list of `warnings: list[str]` containing any non-fatal anomalies

#### Scenario: All-absent no-op
- **WHEN** the helper is called for a change whose artifacts are already gone
- **THEN** the return value SHALL report `worktree_removed=False`, `branch_removed=False`
- **AND** the `warnings` list SHALL be empty


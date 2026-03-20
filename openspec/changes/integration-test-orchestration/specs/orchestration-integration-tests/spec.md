# Spec: Orchestration Integration Tests

## ADDED Requirements

## IN SCOPE
- Merge pipeline integration tests with real git repos (conflict detection, auto-resolve, fingerprint dedup, already-merged detection)
- Verify gate logic tests (dirty worktree handling, retry counting, stuck status recovery)
- State machine transition tests (dependency cascade, missing worktree recovery, status round-trip)
- Stub CLI scripts for set-merge, openspec, set-close
- Reusable pytest fixtures for git repo setup with branches and orchestration state
- Tests run without LLM/API calls, under 30 seconds total

## OUT OF SCOPE
- E2E tests with real Claude API calls (separate Layer 2 effort)
- Testing the sentinel process or bash orchestrator
- Testing the web API or GUI components
- Performance benchmarks or load testing
- Testing actual LLM conflict resolution quality

### Requirement: Merge conflict detection and status transition
The merge pipeline SHALL detect git merge conflicts and transition the change status to `merge-blocked`.

#### Scenario: Clean merge succeeds
- **WHEN** a change branch has no conflicts with main
- **THEN** merge_change() returns success=True, status="merged"
- **AND** the state file shows status="merged"

#### Scenario: Conflicting merge detected
- **WHEN** two changes modify the same file and the first is merged
- **THEN** merge_change() for the second returns success=False, status="merge-blocked"

#### Scenario: No conflict markers on main after merge
- **WHEN** any merge completes successfully
- **THEN** no file on main contains conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)

### Requirement: Already-merged branch detection
The merge pipeline SHALL detect branches that are already merged and skip them gracefully.

#### Scenario: Branch is ancestor of HEAD
- **WHEN** a change branch has already been merged into main
- **THEN** merge_change() returns status="merged", smoke_result="skip_merged"
- **AND** the change is removed from merge_queue

#### Scenario: Branch deleted
- **WHEN** a change branch no longer exists (deleted after manual merge)
- **THEN** merge_change() returns status="merged", smoke_result="skip_merged"

### Requirement: Conflict fingerprint deduplication
The merge pipeline SHALL track conflict fingerprints to avoid retrying identical conflicts.

#### Scenario: Same conflict twice
- **WHEN** a merge conflict produces the same fingerprint as the previous attempt
- **THEN** the change is marked merge-blocked immediately without consuming additional retries

#### Scenario: Different conflict after rebase
- **WHEN** a merge conflict produces a different fingerprint than the previous attempt
- **THEN** the merge is retried (up to MAX_MERGE_RETRIES)

### Requirement: Generated file auto-resolution
The merge pipeline SHALL auto-resolve conflicts in generated files (.claude/*, lockfiles) without blocking.

#### Scenario: .claude/activity.json conflict
- **WHEN** two branches both modify .claude/activity.json
- **THEN** the merge succeeds using the "ours" strategy for generated files

### Requirement: Merge queue drain ordering
The merge queue SHALL be drained sequentially, with each merge seeing the result of previous merges.

#### Scenario: Three changes in queue
- **WHEN** three non-conflicting changes are in the merge queue
- **THEN** all three are merged sequentially
- **AND** each subsequent merge sees the prior merge's changes on main

### Requirement: Dependency cascade on failure
The state machine SHALL cascade failure to all transitive dependents when a change fails.

#### Scenario: Single dependency fails
- **WHEN** change A fails and change B depends_on A
- **THEN** change B is automatically marked as "failed" (cascaded)

#### Scenario: Transitive dependency chain
- **WHEN** change A fails, B depends_on A, C depends_on B
- **THEN** both B and C are marked as "failed" (cascaded)

#### Scenario: Partial dependency failure
- **WHEN** change A fails but change C has no dependency on A
- **THEN** change C remains in its current status (not affected)

### Requirement: Dependency satisfaction dispatch
The state machine SHALL only dispatch changes whose dependencies are all satisfied (merged).

#### Scenario: Dependency satisfied
- **WHEN** change A is merged and change B depends_on A
- **THEN** change B becomes dispatchable

#### Scenario: Dependency not yet satisfied
- **WHEN** change A is still running and change B depends_on A
- **THEN** change B remains pending (not dispatchable)

### Requirement: Dirty worktree handling before verify
The verify pipeline SHALL handle untracked and modified files before running gates.

#### Scenario: Untracked files auto-committed
- **WHEN** the worktree has untracked files (e.g., .eslintignore)
- **THEN** they are auto-committed before verify gates run

#### Scenario: node_modules ignored in dirty check
- **WHEN** node_modules/ contains modified files (symlink changes from pnpm install)
- **THEN** git_has_uncommitted_work() returns False (ignores framework noise)

### Requirement: Verify gate exception recovery
The verify pipeline SHALL NOT leave changes stuck in "verifying" status when a gate throws an exception.

#### Scenario: Gate throws exception
- **WHEN** a verify gate (e.g., spec_verify) raises an unhandled exception
- **THEN** the change status transitions to a recoverable state (retry or failed)
- **AND** the change does NOT remain in "verifying" status indefinitely

### Requirement: Missing worktree recovery
The state machine SHALL handle missing worktrees gracefully instead of crashing.

#### Scenario: Worktree path deleted but state references it
- **WHEN** a change's worktree_path points to a non-existent directory
- **THEN** the system does NOT crash
- **AND** the change can be re-dispatched or marked failed

### Requirement: Post-merge sync ordering
After a successful merge, worktree sync SHALL happen AFTER archive, not before.

#### Scenario: Sync after archive
- **WHEN** merge_change() succeeds
- **THEN** _sync_running_worktrees() is called AFTER archive_change()
- **AND** synced worktrees receive the archive commit

### Requirement: State persistence round-trip
Orchestration state SHALL survive save/load cycles without data loss.

#### Scenario: Full round-trip
- **WHEN** state is saved to JSON and loaded back
- **THEN** all change statuses, timestamps, token counts, and extras are preserved exactly

#### Scenario: Unknown fields preserved
- **WHEN** state JSON contains fields not in the Change dataclass
- **THEN** they are preserved in the extras dict through save/load cycles

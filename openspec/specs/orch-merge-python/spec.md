## ADDED Requirements

### Requirement: Python merge pipeline replaces bash
The Python `merger.py:merge_change()` SHALL be the live merge implementation, called directly by the Python monitor loop (not via set-orch-core CLI subprocess).

#### Scenario: Merge triggered from Python monitor
- **WHEN** the Python monitor loop detects a change ready for merge
- **THEN** it SHALL call `merger.merge_change()` as a Python function call
- **AND** the merge SHALL execute the full pipeline: pre-merge hook → branch check → set-merge → post-merge validation

### Requirement: Python merge executes hooks via subprocess
The Python merge pipeline SHALL execute user-defined hook scripts (pre_merge, post_merge, on_fail) via `subprocess_utils.run_command()`.

#### Scenario: Pre-merge hook execution
- **WHEN** `hook_pre_merge` directive is set
- **THEN** `merger.merge_change()` SHALL run the hook script before attempting merge
- **AND** if the hook returns non-zero, the merge SHALL be aborted

#### Scenario: Post-merge hook execution
- **WHEN** `hook_post_merge` directive is set and merge succeeds
- **THEN** `merger.merge_change()` SHALL run the hook script after merge completion

### Requirement: Python merge updates coverage status
The Python merge pipeline SHALL update requirement coverage status after successful merges.

#### Scenario: Coverage update after merge
- **WHEN** a change is successfully merged
- **THEN** `merger.merge_change()` SHALL call `digest.update_coverage_status()` to mark associated requirements as covered

### Requirement: Python merge syncs running worktrees
After a successful merge to main, the Python merge pipeline SHALL sync all other running worktrees with the updated main branch.

#### Scenario: Worktree sync after merge
- **WHEN** a change is merged to main
- **THEN** `merger.merge_change()` SHALL iterate over all changes with status "running"
- **AND** call `dispatcher.sync_worktree_with_main()` for each running worktree

### Requirement: Python merge fixes base build with LLM
When a merge causes the base build to break, the Python merge pipeline SHALL attempt an LLM-assisted fix.

#### Scenario: Post-merge build failure with LLM fix
- **WHEN** a post-merge build check fails
- **THEN** `merger.merge_change()` SHALL call `builder.fix_base_build()` to attempt auto-fix
- **AND** if fix succeeds, it SHALL commit the fix and continue
- **AND** if fix fails, it SHALL log the failure but not block the merge

### Requirement: Python merge handles retry queue
The Python `merger.retry_merge_queue()` SHALL drain the merge queue, attempting merges for queued changes and handling conflicts with deduplication.

#### Scenario: Merge queue retry with conflict dedup
- **WHEN** `retry_merge_queue()` is called
- **THEN** it SHALL attempt merge for each queued change
- **AND** it SHALL track conflict fingerprints to avoid infinite retry of the same conflict
- **AND** it SHALL mark changes as "merge-blocked" after repeated conflict failures

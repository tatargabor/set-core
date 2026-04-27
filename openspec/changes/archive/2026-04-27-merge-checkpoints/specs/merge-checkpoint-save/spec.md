## ADDED Requirements

## IN SCOPE
- Saving checkpoint metadata (manifest entry) after each successful merge
- Snapshotting progress files (coverage-merged.json, review-findings.jsonl) at merge time
- Storing checkpoints in `set/orchestration/checkpoints/` within the consumer project
- Git-committing checkpoint data as part of the archive commit

## OUT OF SCOPE
- Full orchestration-state.json snapshots (contains stale ephemeral data — PIDs, worktree paths)
- Manual/on-demand checkpoint creation (trigger is always post-merge)
- Checkpoint pruning/rotation (keep all by default, can be added later)
- Phase-boundary checkpoints (only merge triggers)

### Requirement: Checkpoint manifest entry after merge
The merger SHALL append a checkpoint record to `set/orchestration/checkpoints/manifest.jsonl` after a successful merge + archive. Each record SHALL contain: change name, git commit SHA (HEAD after archive), phase number, ISO timestamp, and list of all merged changes up to this point.

#### Scenario: First change merges
- **WHEN** change `setup-routing` is the first change to merge successfully
- **THEN** `checkpoints/manifest.jsonl` is created with one record containing `change: "setup-routing"`, the current HEAD SHA, `phase: 1`, and `merged_so_far: ["setup-routing"]`

#### Scenario: Subsequent change merges
- **WHEN** change `add-auth` merges after `setup-routing`
- **THEN** a new record is appended with `change: "add-auth"`, updated HEAD SHA, current phase, and `merged_so_far: ["setup-routing", "add-auth"]`

#### Scenario: Manifest survives git reset
- **WHEN** recovery performs `git reset --hard` to an earlier checkpoint
- **THEN** the manifest file is preserved (saved to temp and restored, same as archive dirs)

### Requirement: Progress file snapshot at merge time
The merger SHALL copy progress files into a per-checkpoint directory at `set/orchestration/checkpoints/orch-{change_name}/` immediately after the archive commit.

#### Scenario: Coverage and findings are snapshot
- **WHEN** change `cart-system` merges and `coverage-merged.json` and `review-findings.jsonl` exist
- **THEN** both files are copied to `checkpoints/orch-cart-system/`

#### Scenario: Missing progress files
- **WHEN** a change merges but `coverage-merged.json` does not exist yet (first change, no coverage)
- **THEN** the checkpoint directory is still created, containing only the files that exist

#### Scenario: Checkpoint data included in archive commit
- **WHEN** the checkpoint files are written
- **THEN** they are staged and included in the same git commit as the openspec archive (or a separate checkpoint commit immediately after)

### Requirement: Hook point in merger pipeline
The checkpoint save SHALL execute after `archive_change()` and `_final_token_collect()` but before `_remove_from_merge_queue()`, at approximately line 654-659 of merger.py.

#### Scenario: Hook placement
- **WHEN** `merge_change()` reaches the post-archive section
- **THEN** `_save_merge_checkpoint()` is called with state_file, change_name, and project_path
- **THEN** execution continues to `_remove_from_merge_queue()` regardless of checkpoint save success (checkpoint failure is WARNING, not fatal)

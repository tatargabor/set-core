# Worktree Harvest Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Post-merge worktree harvest
The system SHALL copy valuable worktree-local files to a persistent archive location after a successful merge, independent of worktree retention policy.

#### Scenario: Successful merge triggers harvest
- **WHEN** `cleanup_worktree()` is called after a successful merge
- **THEN** `harvest_worktree(change_name, wt_path, project_path)` is invoked AFTER the existing `_archive_worktree_logs()` and `_archive_test_artifacts()` calls and BEFORE any retention-policy-driven worktree removal
- **THEN** the harvest copies each of the following files if present: `.set/reflection.md`, `.set/loop-state.json`, `.set/activity.json`, `.claude/review-findings.md`
- **THEN** the worktree itself remains untouched (harvest is a copy, not a move)

#### Scenario: Worktree missing optional files
- **WHEN** one or more of the harvested files is absent in the worktree
- **THEN** missing files are silently skipped (they are all marked optional)
- **THEN** the harvest completes successfully with a reduced file list
- **THEN** the `.harvest-meta.json` records only the files that were actually copied

#### Scenario: All harvested files missing
- **WHEN** none of the target files exist in the worktree
- **THEN** the harvest directory is still created
- **THEN** the `.harvest-meta.json` is still written with `files: []`

### Requirement: Harvest destination path
The system SHALL compute a deterministic destination path from the change name, with collision defense via a timestamp suffix.

#### Scenario: First harvest for a change
- **WHEN** `harvest_worktree()` is called for a change whose harvest directory does not yet exist
- **THEN** the destination is `<orchestration_dir>/archives/worktrees/<change-name>/`

#### Scenario: Collision with existing harvest
- **WHEN** `harvest_worktree()` is called for a change whose harvest directory already exists (e.g., same change name reused across runs)
- **THEN** the destination becomes `<orchestration_dir>/archives/worktrees/<change-name>.<UTC-YYYYMMDDTHHMMSSZ>/`
- **THEN** a WARNING is logged noting the collision and the fallback path

### Requirement: Harvest metadata sidecar
The system SHALL write a `.harvest-meta.json` file inside each harvest directory describing the harvest operation.

#### Scenario: Metadata contents
- **WHEN** a harvest completes
- **THEN** a `.harvest-meta.json` file is written with keys: `harvested_at` (ISO 8601 UTC), `reason` (default `"merge"`), `wt_path` (absolute path to source worktree), `wt_name` (the change name), `files` (list of harvested relative paths), `commit` (HEAD commit hash from the worktree, or null if unavailable)
- **THEN** the sidecar is JSON-formatted and pretty-printed with a 2-space indent

### Requirement: Non-blocking harvest
The system SHALL NOT allow harvest failures to block or fail the merge pipeline.

#### Scenario: Harvest throws an exception
- **WHEN** `harvest_worktree()` raises an exception (e.g., permission error, disk full)
- **THEN** the exception is caught at the call site in `cleanup_worktree()`
- **THEN** a WARNING is logged with the change name and exception details
- **THEN** the merge cleanup proceeds normally without the harvest
- **THEN** no state.json field is modified to indicate harvest failure (harvest is observational only)

#### Scenario: Harvest runs successfully
- **WHEN** `harvest_worktree()` completes without exception
- **THEN** an INFO log records the change name, destination path, and count of harvested files

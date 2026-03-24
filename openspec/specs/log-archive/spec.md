## ADDED Requirements

### Requirement: Archive worktree logs before cleanup
Worktree agent iteration logs (`.claude/logs/*.log`) are copied to a persistent location before `git worktree remove`.

#### Scenario: Successful merge triggers log archive
- **WHEN** a change is merged and the worktree is about to be removed
- **THEN** all files from `<worktree>/.claude/logs/` are copied to `set/orchestration/logs/<change-name>/`
- **THEN** the worktree removal proceeds normally

#### Scenario: Worktree has no logs
- **WHEN** the worktree's `.claude/logs/` directory doesn't exist or is empty
- **THEN** no archive directory is created, no error is raised

#### Scenario: Archive directory already exists (redispatch)
- **WHEN** a change was redispatched and logs from a previous worktree already exist in the archive
- **THEN** new logs are added alongside existing ones (no overwrite)
- **THEN** files are prefixed or placed in subdirectories to avoid name collisions

### Requirement: API serves archived logs
The log API falls back to the archive when the worktree is gone.

#### Scenario: Request logs for a merged change
- **WHEN** `GET /api/{project}/changes/{name}/logs` is called for a merged change
- **THEN** if the worktree is gone, the API checks `set/orchestration/logs/<change-name>/`
- **THEN** returns the archived log file list

#### Scenario: Read an archived log file
- **WHEN** `GET /api/{project}/changes/{name}/log/{filename}` is called
- **THEN** the API serves from the archive directory if the worktree doesn't exist

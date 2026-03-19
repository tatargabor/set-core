# ralph-auto-detect Specification

## Purpose
TBD - created by archiving change mcp-server-documentation. Update Purpose after archive.
## Requirements
### Requirement: Auto-detect change-id from current worktree
The set-loop commands SHALL automatically detect the change-id when running inside a worktree directory, making the change-id parameter optional.

#### Scenario: Start without change-id in worktree
- **WHEN** user runs `set-loop start "task description"` inside a worktree
- **THEN** system detects change-id from directory name pattern `<project>-wt-<change-id>`
- **AND** starts Ralph loop for that change-id

#### Scenario: Start without change-id outside worktree
- **WHEN** user runs `set-loop start "task description"` outside a worktree
- **THEN** system shows error "Not in a worktree or change-id not specified"
- **AND** suggests providing change-id explicitly

#### Scenario: Explicit change-id always works
- **WHEN** user provides explicit change-id `set-loop start my-change "task"`
- **THEN** system uses the provided change-id
- **AND** does NOT use pwd detection

### Requirement: All set-loop commands support auto-detect
All set-loop commands SHALL support change-id auto-detection consistently.

#### Scenario: Status without change-id
- **WHEN** user runs `set-loop status` inside worktree
- **THEN** shows status for current worktree's Ralph loop

#### Scenario: Stop without change-id
- **WHEN** user runs `set-loop stop` inside worktree
- **THEN** stops the Ralph loop for current worktree

#### Scenario: History without change-id
- **WHEN** user runs `set-loop history` inside worktree
- **THEN** shows history for current worktree's Ralph loop

#### Scenario: Monitor without change-id
- **WHEN** user runs `set-loop monitor` inside worktree
- **THEN** monitors the Ralph loop for current worktree


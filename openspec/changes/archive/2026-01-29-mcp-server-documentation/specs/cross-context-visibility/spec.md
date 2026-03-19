## ADDED Requirements

### Requirement: List all worktrees via MCP
The system SHALL expose a `list_worktrees()` MCP tool that returns all worktrees across all projects.

#### Scenario: List worktrees with Ralph indicator
- **WHEN** agent calls `list_worktrees()`
- **THEN** returns list grouped by project
- **AND** each worktree shows branch name
- **AND** worktrees with active Ralph show indicator (e.g., "[Ralph running]")

#### Scenario: No active worktrees
- **WHEN** no worktrees exist (only main repos)
- **THEN** returns "No active worktrees"

### Requirement: Query team status via MCP
The system SHALL expose a `get_team_status()` MCP tool that returns team member activity.

#### Scenario: Team members active
- **WHEN** agent calls `get_team_status()`
- **THEN** returns list of team members
- **AND** each entry shows: name, agent_status (idle/working), change_id

#### Scenario: Team status unavailable
- **WHEN** GUI is not running or team sync disabled
- **THEN** returns "Team status not available"

### Requirement: Query worktree tasks via MCP
The system SHALL expose a `get_worktree_tasks()` MCP tool that returns tasks.md content.

#### Scenario: Tasks file exists
- **WHEN** agent calls `get_worktree_tasks(worktree_path)`
- **THEN** returns content of tasks.md from that worktree
- **AND** searches in `openspec/changes/*/tasks.md` or `.set-core/tasks.md`

#### Scenario: No tasks file
- **WHEN** no tasks.md exists in worktree
- **THEN** returns "No tasks file found in this worktree"

### Requirement: Cross-context visibility enables coordination
The system SHALL enable agents to see each other's work for coordination purposes.

#### Scenario: Check before merge
- **WHEN** agent in worktree A wants to merge
- **THEN** agent can query `get_ralph_status()` to check if Ralph runs in other worktrees
- **AND** can decide to wait or proceed based on status

#### Scenario: Avoid duplicate work
- **WHEN** agent starts new task
- **THEN** agent can query `list_worktrees()` to see existing work
- **AND** can check if similar change already in progress

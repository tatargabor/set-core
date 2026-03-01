## ADDED Requirements

### Requirement: Query agent activity via MCP

The system SHALL expose a `get_activity()` MCP tool that returns current activity for all local worktrees.

#### Scenario: Activity data available

- **WHEN** agent calls `get_activity()`
- **THEN** returns list of all worktrees that have `.claude/activity.json`
- **AND** each entry shows: worktree path, skill, skill_args, broadcast, updated_at
- **AND** entries are sorted by updated_at (most recent first)

#### Scenario: Filter by change_id

- **WHEN** agent calls `get_activity(change_id="add-oauth")`
- **THEN** returns only the activity entry for the worktree working on "add-oauth"

#### Scenario: No activity files exist

- **WHEN** no worktrees have `.claude/activity.json`
- **THEN** returns "No agent activity found"

#### Scenario: Stale activity marked

- **GIVEN** a worktree has `.claude/activity.json` with `updated_at` older than 5 minutes
- **WHEN** `get_activity()` returns this entry
- **THEN** the entry includes `stale: true`

### Requirement: Activity enables coordination

The system SHALL enable agents to use activity data for coordination decisions.

#### Scenario: Detect file overlap before editing

- **GIVEN** Agent-A has activity with `modified_files: ["src/auth/oauth.py"]`
- **WHEN** Agent-B calls `get_activity()` before editing `src/auth/oauth.py`
- **THEN** Agent-B can see that Agent-A is modifying the same file
- **AND** can decide to wait or coordinate

#### Scenario: Detect skill overlap

- **GIVEN** Agent-A has activity with `skill: "opsx:apply"`, `skill_args: "add-oauth"`
- **WHEN** Agent-B calls `get_activity()` before starting work on "add-oauth"
- **THEN** Agent-B can see that Agent-A is already applying changes for "add-oauth"

## ADDED Requirements

### Requirement: Local Activity File

The system SHALL maintain a local activity file at `.claude/activity.json` in each worktree, tracking the current agent's skill and intent.

#### Scenario: Activity file written on skill start

- **GIVEN** a Claude hook is configured for PreToolUse on the Skill tool
- **WHEN** an agent invokes a skill (e.g., `opsx:apply`, `opsx:explore`)
- **THEN** `.claude/activity.json` is written with: `skill`, `skill_args`, `updated_at`
- **AND** existing `broadcast` and `modified_files` fields are preserved

#### Scenario: Activity file format

- **WHEN** `.claude/activity.json` exists
- **THEN** it SHALL contain a JSON object with fields:
  - `skill` (string): Active skill name (e.g., "opsx:apply")
  - `skill_args` (string, optional): Skill arguments (e.g., "add-oauth")
  - `broadcast` (string, optional): Free-form description of current work
  - `modified_files` (array of string, optional): Files being modified
  - `updated_at` (string): ISO8601 timestamp of last update

#### Scenario: Activity file absent

- **GIVEN** no agent has run a skill in this worktree
- **WHEN** any consumer reads `.claude/activity.json`
- **THEN** the file does not exist
- **AND** the consumer treats this as "no activity"

### Requirement: Hook-Based Auto-Tracking

The system SHALL automatically track agent skill usage via a Claude PreToolUse hook.

#### Scenario: Hook fires on Skill tool

- **GIVEN** `.claude/settings.json` configures a PreToolUse hook for the Skill tool
- **WHEN** an agent invokes the Skill tool with `{"skill": "opsx:apply", "args": "add-oauth"}`
- **THEN** the hook script `.claude/hooks/activity-track.sh` is executed
- **AND** `.claude/activity.json` is updated with skill="opsx:apply", skill_args="add-oauth"

#### Scenario: Hook throttling

- **GIVEN** the hook fired less than 10 seconds ago
- **WHEN** the hook fires again
- **THEN** the write is skipped (no file update)
- **AND** the hook exits immediately

#### Scenario: Hook runs async

- **WHEN** the hook script executes
- **THEN** it SHALL run in the background (non-blocking)
- **AND** it SHALL NOT delay the agent's tool execution

#### Scenario: Hook configuration in project settings

- **WHEN** a project has activity tracking enabled
- **THEN** `.claude/settings.json` SHALL contain a PreToolUse hook entry for the Skill tool
- **AND** the hook command points to `.claude/hooks/activity-track.sh`

### Requirement: Broadcast Skill

The system SHALL provide a `/context broadcast` skill for agents to announce their current work.

#### Scenario: Set broadcast message

- **GIVEN** an agent is working in a worktree
- **WHEN** the agent runs `/context broadcast "Adding Google OAuth provider"`
- **THEN** `.claude/activity.json` is updated with `broadcast: "Adding Google OAuth provider"`
- **AND** `updated_at` is set to current time

#### Scenario: Broadcast overwrites previous

- **GIVEN** `.claude/activity.json` has `broadcast: "old message"`
- **WHEN** the agent runs `/context broadcast "new message"`
- **THEN** `broadcast` is replaced with "new message"
- **AND** other fields (skill, skill_args) are preserved

### Requirement: Status Skill

The system SHALL provide a `/context status` skill to display all agents' current activities.

#### Scenario: Show local agents' activity

- **GIVEN** Agent-A (worktree-1) has activity: skill=opsx:apply, broadcast="Adding OAuth"
- **AND** Agent-B (worktree-2) has activity: skill=opsx:explore
- **WHEN** any agent runs `/context status`
- **THEN** output shows both agents' activities with worktree path, skill, broadcast, and relative timestamp

#### Scenario: Show remote agents' activity

- **GIVEN** team-sync is enabled
- **AND** remote member "peter@laptop" has activity in `members/peter@laptop.json`
- **WHEN** agent runs `/context status`
- **THEN** output includes remote member's activity
- **AND** remote entries are marked with source indicator (e.g., "(remote)")

#### Scenario: Stale activity detection

- **GIVEN** an activity file has `updated_at` older than 5 minutes
- **WHEN** `/context status` displays this entry
- **THEN** the entry is shown with "(stale)" indicator

#### Scenario: No activity anywhere

- **GIVEN** no activity files exist locally
- **AND** no team members have activity data
- **WHEN** agent runs `/context status`
- **THEN** output shows "No active agents found"

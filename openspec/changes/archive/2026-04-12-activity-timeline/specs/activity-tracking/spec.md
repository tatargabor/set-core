## MODIFIED Requirements

### Requirement: Broadcast Skill

The system SHALL provide a `/wt:broadcast` skill for agents to announce their current work.

#### Scenario: Set broadcast message

- **GIVEN** an agent is working in a worktree
- **WHEN** the agent runs `/wt:broadcast "Adding Google OAuth provider"`
- **THEN** `.claude/activity.json` is updated with `broadcast: "Adding Google OAuth provider"`
- **AND** `updated_at` is set to current time

#### Scenario: Broadcast overwrites previous

- **GIVEN** `.claude/activity.json` has `broadcast: "old message"`
- **WHEN** the agent runs `/wt:broadcast "new message"`
- **THEN** `broadcast` is replaced with "new message"
- **AND** other fields (skill, skill_args) are preserved

### Requirement: Status Skill

The system SHALL provide a `/wt:status` skill to display all agents' current activities.

#### Scenario: Show local agents' activity

- **GIVEN** Agent-A (worktree-1) has activity: skill=opsx:apply, broadcast="Adding OAuth"
- **AND** Agent-B (worktree-2) has activity: skill=opsx:explore
- **WHEN** any agent runs `/wt:status`
- **THEN** output shows both agents' activities with worktree path, skill, broadcast, and relative timestamp

#### Scenario: Show remote agents' activity

- **GIVEN** team-sync is enabled
- **AND** remote member "peter@laptop" has activity in `members/peter@laptop.json`
- **WHEN** agent runs `/wt:status`
- **THEN** output includes remote member's activity
- **AND** remote entries are marked with source indicator (e.g., "(remote)")

#### Scenario: Show unread message count in status

- **GIVEN** agent has 3 unread directed messages
- **WHEN** agent runs `/wt:status`
- **THEN** output includes "3 unread messages" indicator
- **AND** suggests running `/wt:inbox` to read them

#### Scenario: Stale activity detection

- **GIVEN** an activity file has `updated_at` older than 5 minutes
- **WHEN** `/wt:status` displays this entry
- **THEN** the entry is shown with "(stale)" indicator

#### Scenario: No activity anywhere

- **GIVEN** no activity files exist locally
- **AND** no team members have activity data
- **WHEN** agent runs `/wt:status`
- **THEN** output shows "No active agents found"

## ADDED Requirements

### Requirement: Idle detection events

The system SHALL emit IDLE_START and IDLE_END events when no change activity is detected.

#### Scenario: Idle period detected

- **WHEN** the watchdog detects no activity across all watched changes for more than 60 seconds
- **THEN** an `IDLE_START` event SHALL be emitted to the EventBus
- **AND** when any activity resumes, an `IDLE_END` event SHALL be emitted

#### Scenario: Idle events include context

- **WHEN** an IDLE_START event is emitted
- **THEN** the event data SHALL include `watched_changes` (list of change names being monitored)

### Requirement: Manual stop/resume events

The system SHALL emit MANUAL_STOP and MANUAL_RESUME events when users pause or resume changes.

#### Scenario: User pauses a change

- **WHEN** `pause_change()` is called for change "add-auth"
- **THEN** a `MANUAL_STOP` event SHALL be emitted with `change=add-auth`

#### Scenario: User resumes a change

- **WHEN** `resume_change()` is called for change "add-auth"
- **THEN** a `MANUAL_RESUME` event SHALL be emitted with `change=add-auth`

### Requirement: Watchdog escalation events

The system SHALL emit WATCHDOG_ESCALATION events on escalation level transitions.

#### Scenario: Escalation level increases

- **WHEN** the watchdog escalates a change from level 0 to level 1 (restart)
- **THEN** a `WATCHDOG_ESCALATION` event SHALL be emitted with `change`, `data.from_level`, `data.to_level`, and `data.action` (restart/redispatch/fail)

### Requirement: Iteration boundary events

The system SHALL emit ITERATION_START and ITERATION_END events for Ralph loop iterations.

#### Scenario: Iteration starts

- **WHEN** a new Ralph loop iteration begins
- **THEN** an `ITERATION_START` event SHALL be emitted with `change` and `data.iteration` (iteration number)

#### Scenario: Iteration ends

- **WHEN** a Ralph loop iteration completes
- **THEN** an `ITERATION_END` event SHALL be emitted with `change`, `data.iteration`, `data.duration_ms`, and `data.tokens_used`

### Requirement: Conflict resolution events

The system SHALL emit CONFLICT_RESOLUTION_START and CONFLICT_RESOLUTION_END events during merge conflict handling.

#### Scenario: Conflict resolution begins

- **WHEN** the merger detects conflicting files and starts resolution
- **THEN** a `CONFLICT_RESOLUTION_START` event SHALL be emitted with `change` and `data.conflicted_files` (list of file paths)

#### Scenario: Conflict resolution completes

- **WHEN** conflict resolution finishes (success or failure)
- **THEN** a `CONFLICT_RESOLUTION_END` event SHALL be emitted with `change`, `data.result` (resolved/failed), and `data.duration_ms`

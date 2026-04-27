# Team Sync Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## MODIFIED Requirements

### Requirement: GUI Team Status Display

The GUI SHALL display team member status in the main window, including communication activity indicators.

#### Scenario: Team label when enabled

- **GIVEN** team sync is enabled in settings
- **WHEN** team data is received from TeamWorker
- **THEN** a team status label is shown with active/waiting members

#### Scenario: Active members display

- **GIVEN** Peter has status "active" (running agent)
- **WHEN** team label is displayed
- **THEN** Peter is shown with green indicator

#### Scenario: Waiting members display

- **GIVEN** Anna has status "waiting"
- **WHEN** team label is displayed
- **THEN** Anna is shown with yellow indicator

#### Scenario: Conflict warning in label

- **GIVEN** a conflict exists on change "add-feature"
- **WHEN** team label is displayed
- **THEN** conflict is shown: "! add-feature"

#### Scenario: Team label hidden when disabled

- **GIVEN** team sync is disabled in settings
- **WHEN** the Control Center is displayed
- **THEN** the team label is hidden

## Requirements

### Requirement: Communication Activity Indicators on Team Rows

The GUI SHALL display subtle communication activity indicators on team worktree rows.

#### Scenario: Broadcast activity indicator

- **GIVEN** a remote agent updated their broadcast within the last 60 seconds
- **WHEN** the team worktree row is displayed
- **THEN** a broadcast indicator (📡) is shown in the row
- **AND** a tooltip on the indicator shows the broadcast message text

#### Scenario: Directed message activity indicator

- **GIVEN** a directed message was sent to/from this worktree within the last 60 seconds
- **WHEN** the team worktree row is displayed
- **THEN** a message indicator (💬) is shown in the row
- **AND** a tooltip shows "Message from/to <sender>"

#### Scenario: No recent activity

- **GIVEN** no broadcast or message activity within the last 60 seconds
- **WHEN** the team worktree row is displayed
- **THEN** no communication indicator is shown (clean default)

#### Scenario: Broadcast and directed message distinguishable

- **GIVEN** a team row has both recent broadcast and directed message
- **WHEN** the row is displayed
- **THEN** both indicators are shown (📡💬)
- **AND** each has its own tooltip

### Requirement: Broadcast Field in Team Status Cache

The GUI team worker SHALL propagate broadcast messages to the `team_status.json` cache for MCP server access.

#### Scenario: Broadcast propagated to cache

- **GIVEN** a remote member has `activity.broadcast` set in their member JSON
- **WHEN** the GUI writes `team_status.json` cache
- **THEN** the broadcast field is included in the cache entry

#### Scenario: Activity data propagated to cache

- **GIVEN** a remote member has full `activity` object (skill, broadcast, updated_at)
- **WHEN** the GUI writes `team_status.json` cache
- **THEN** the full activity object is included in the cache entry

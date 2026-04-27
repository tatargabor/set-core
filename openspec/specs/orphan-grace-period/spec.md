# Orphan Grace Period Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Grace period before orphan kill

The system SHALL NOT kill an orphan agent until it has been detected as orphan in at least 3 consecutive `cleanup_orphan_agents()` invocations AND at least 15 seconds have elapsed since the first orphan detection for that PID.

#### Scenario: Transient editor detection failure
- **WHEN** a waiting agent is detected as orphan for the first time
- **THEN** the system records the PID, current timestamp, and count=1 in a marker file
- **AND** the agent is NOT killed

#### Scenario: Second consecutive orphan detection
- **WHEN** a waiting agent is detected as orphan and its marker file shows count=1
- **THEN** the system increments the count to 2
- **AND** the agent is NOT killed

#### Scenario: Third detection but under 15 seconds
- **WHEN** a waiting agent is detected as orphan for the 3rd consecutive time
- **AND** fewer than 15 seconds have elapsed since first detection
- **THEN** the system increments the count to 3
- **AND** the agent is NOT killed

#### Scenario: Kill after threshold met
- **WHEN** a waiting agent is detected as orphan
- **AND** the marker file shows count >= 3
- **AND** at least 15 seconds have elapsed since first detection
- **THEN** the system kills the agent (SIGTERM)
- **AND** removes the marker file
- **AND** removes the skill file

### Requirement: Grace period reset on safe detection

The system SHALL reset the orphan grace period tracking for an agent whenever it passes any safety check (editor is open, Ralph loop is active, agent has active TTY with shell, or agent is in running/compacting status).

#### Scenario: Editor reopened during grace period
- **WHEN** a waiting agent has an orphan marker file with count=2
- **AND** on the next `cleanup_orphan_agents()` call, `is_editor_open()` returns true
- **THEN** the marker file for that PID is deleted
- **AND** the agent is preserved

#### Scenario: Agent becomes active during grace period
- **WHEN** a waiting agent has an orphan marker file
- **AND** the agent transitions to "running" or "compacting" status
- **THEN** the marker file for that PID is deleted

### Requirement: Stale marker cleanup

The system SHALL remove orphan marker files for PIDs that no longer exist as running processes.

#### Scenario: Process died naturally
- **WHEN** `cleanup_orphan_agents()` runs
- **AND** a marker file exists for PID 12345
- **AND** PID 12345 is no longer a running process
- **THEN** the marker file for PID 12345 is deleted

### Requirement: Marker file storage

The system SHALL store orphan detection state in `.set-core/orphan-detect/<pid>` files within each worktree directory. Each file SHALL contain `<first_seen_timestamp>:<count>`.

#### Scenario: Marker file format
- **WHEN** an orphan agent with PID 12345 is first detected at Unix timestamp 1707400000
- **THEN** the file `.set-core/orphan-detect/12345` is created with content `1707400000:1`

#### Scenario: Marker file update
- **WHEN** the same agent is detected as orphan again
- **THEN** the file content is updated to `1707400000:2` (timestamp stays, count increments)

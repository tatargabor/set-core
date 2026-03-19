## ADDED Requirements

### Requirement: Editor Window Presence Detection
The system SHALL detect whether an editor window is open for each worktree during status collection.

#### Scenario: Editor window open on Linux with xdotool
- **WHEN** `wt-status` checks a worktree on Linux
- **AND** xdotool is available
- **THEN** `is_editor_open()` SHALL search for windows matching the worktree basename
- **AND** return true if at least one matching window exists

#### Scenario: Editor window open on Linux without xdotool
- **WHEN** `wt-status` checks a worktree on Linux
- **AND** xdotool is NOT available
- **THEN** `is_editor_open()` SHALL scan `/proc/*/cmdline` for editor processes
- **AND** return true if any editor process has CWD matching the worktree path

#### Scenario: No editor window found
- **WHEN** `wt-status` checks a worktree
- **AND** no editor window matches the worktree basename
- **AND** no editor process has CWD in the worktree
- **THEN** `is_editor_open()` SHALL return false

#### Scenario: Editor window detection on macOS
- **WHEN** `wt-status` checks a worktree on macOS
- **THEN** `is_editor_open()` SHALL use osascript to query editor windows
- **AND** return true if a window title contains the worktree basename

### Requirement: Orphan Agent Automatic Cleanup
The system SHALL automatically terminate Claude agent processes that have no associated editor window and no active Ralph loop.

#### Scenario: Kill orphan waiting agent
- **WHEN** `wt-status` detects an agent with status "waiting" in a worktree
- **AND** no editor window is open for that worktree
- **AND** no Ralph loop is active for that worktree (loop-state.json status is not "running")
- **THEN** the agent process SHALL be sent SIGTERM
- **AND** the agent SHALL NOT appear in the status output

#### Scenario: Preserve agent with Ralph loop
- **WHEN** `wt-status` detects an agent in a worktree with no editor window
- **AND** a Ralph loop IS active for that worktree
- **THEN** the agent SHALL NOT be killed
- **AND** the agent SHALL appear in the status output normally

#### Scenario: Preserve running agent without editor
- **WHEN** `wt-status` detects an agent with status "running" (session mtime < 10s) in a worktree
- **AND** no editor window is open
- **THEN** the agent SHALL NOT be killed (it may be running in a headless terminal)

#### Scenario: Multiple orphan agents in one worktree
- **WHEN** `wt-status` detects multiple waiting agents in a worktree with no editor
- **AND** no Ralph loop is active
- **THEN** ALL waiting agents SHALL be killed

#### Scenario: Cleanup logging
- **WHEN** an orphan agent is killed
- **THEN** a message SHALL be written to stderr with the PID and worktree path

### Requirement: Orphan Cleanup Respects Skill Files
The system SHALL clean up `.set-core/agents/<pid>.skill` files for killed orphan agents.

#### Scenario: Skill file removed after orphan kill
- **WHEN** an orphan agent with PID N is killed
- **AND** a file `.set-core/agents/N.skill` exists
- **THEN** the skill file SHALL be removed

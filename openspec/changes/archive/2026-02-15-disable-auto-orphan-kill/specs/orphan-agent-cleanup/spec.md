## MODIFIED Requirements

### Requirement: Orphan Agent Automatic Cleanup
The system SHALL detect orphan Claude agent processes (no editor window, no active Ralph loop, no interactive TTY shell) and mark them with status "orphan" in the status output. The system SHALL NOT automatically terminate these processes — cleanup is manual only, via the GUI context menu.

#### Scenario: Detect orphan waiting agent
- **WHEN** `wt-status` detects an agent with status "waiting" in a worktree
- **AND** no editor window is open for that worktree
- **AND** no Ralph loop is active for that worktree
- **AND** no interactive TTY shell is associated with the agent
- **THEN** the agent SHALL appear in the status output with status "orphan"
- **AND** the agent process SHALL NOT be sent any signal

#### Scenario: Preserve agent with Ralph loop
- **WHEN** `wt-status` detects an agent in a worktree with no editor window
- **AND** a Ralph loop IS active for that worktree
- **THEN** the agent SHALL NOT be marked as orphan
- **AND** the agent SHALL appear in the status output normally

#### Scenario: Preserve running agent without editor
- **WHEN** `wt-status` detects an agent with status "running" (session mtime < 10s) in a worktree
- **AND** no editor window is open
- **THEN** the agent SHALL NOT be marked as orphan

#### Scenario: Multiple orphan agents in one worktree
- **WHEN** `wt-status` detects multiple waiting agents in a worktree with no editor
- **AND** no Ralph loop is active
- **THEN** ALL waiting agents SHALL be marked as orphan in the status output
- **AND** none SHALL be automatically killed

### Requirement: Orphan Cleanup Respects Skill Files
The system SHALL NOT automatically clean up `.set-core/agents/<pid>.skill` files. Skill file cleanup only happens when an agent is manually killed via the GUI.

#### Scenario: Skill file preserved for orphan agent
- **WHEN** an orphan agent with PID N exists
- **AND** a file `.set-core/agents/N.skill` exists
- **THEN** the skill file SHALL NOT be automatically removed

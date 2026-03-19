## ADDED Requirements

### Requirement: Claude Activity Logging via Hooks
The system SHALL log Claude agent file operations using Claude Code hooks.

#### Scenario: Log file edit operation
- **WHEN** Claude uses the Edit tool on a file
- **AND** the PostToolUse hook fires
- **THEN** an activity event is logged to `~/.config/set-core/claude-activity.jsonl`
- **AND** the event includes timestamp, tool name, file path, and project context

#### Scenario: Log file read operation
- **WHEN** Claude uses the Read tool on a file
- **AND** the PostToolUse hook fires
- **THEN** an activity event is logged with tool="Read"

#### Scenario: Log file write operation
- **WHEN** Claude uses the Write tool to create a file
- **AND** the PostToolUse hook fires
- **THEN** an activity event is logged with tool="Write"

#### Scenario: Ignore irrelevant paths
- **WHEN** Claude reads a file matching ignore patterns (node_modules/*, .git/*)
- **THEN** no activity event is logged

### Requirement: Hook Setup Command
The system SHALL provide a command to configure Claude Code hooks.

#### Scenario: Setup hooks
- **WHEN** user runs `wt-activity setup`
- **THEN** the PostToolUse hook is added to `~/.claude/settings.json`
- **AND** the hook matches Read, Edit, and Write tools
- **AND** existing settings are preserved

#### Scenario: Remove hooks
- **WHEN** user runs `wt-activity remove`
- **THEN** the wt-activity hooks are removed from settings.json
- **AND** other hooks are preserved

### Requirement: Activity Query Commands
The system SHALL provide commands to query logged activities.

#### Scenario: List today's activities
- **WHEN** user runs `wt-activity list`
- **THEN** all file activities from today are displayed
- **AND** activities show timestamp, tool, and file path

#### Scenario: List activities for specific date
- **WHEN** user runs `wt-activity list --date 2026-01-15`
- **THEN** activities from that date are displayed

#### Scenario: List unique files
- **WHEN** user runs `wt-activity files`
- **THEN** unique file paths worked on today are listed
- **AND** each file shows Read/Edit/Write counts

#### Scenario: Show statistics
- **WHEN** user runs `wt-activity stats`
- **THEN** summary statistics are displayed
- **AND** includes total events, unique files, time span

### Requirement: Claude Activity in Reconstruct Mode
The system SHALL include Claude activity log as a source in reconstruct mode.

#### Scenario: Collect claude-activity for date
- **WHEN** user runs `wt-jira auto --reconstruct`
- **AND** claude-activity log exists for the target date
- **THEN** activities are included with confidence 0.85
- **AND** activities are grouped into work blocks

#### Scenario: Map activities to JIRA tickets
- **WHEN** processing claude-activity events
- **THEN** the system maps file paths to projects via CWD
- **AND** maps projects to JIRA tickets via worktree detection

#### Scenario: Source selection
- **WHEN** user runs `wt-jira auto --sources git,claude-activity`
- **THEN** only git commits and claude-activity are used
- **AND** other sources (zed, vscode, etc.) are excluded

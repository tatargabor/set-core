## ADDED Requirements

### Requirement: Memory indicator button in project header
The project header row SHALL display an [M] button (22x22px, same style as team filter/chat buttons) to the right of existing header buttons. The button color SHALL be purple (`status_compacting`) when shodh-memory is available and has memories, or gray (`status_idle`) when not installed. The tooltip SHALL show memory count and availability status.

#### Scenario: Shodh-memory available with memories
- **WHEN** shodh-memory Python package is importable and the project has memories stored
- **THEN** the [M] button appears in purple with tooltip "Memory: N memories"

#### Scenario: Shodh-memory not installed
- **WHEN** shodh-memory Python package is not importable
- **THEN** the [M] button appears in gray with tooltip "Memory: not installed"

#### Scenario: Button click opens browse dialog
- **WHEN** user clicks the [M] button
- **THEN** the memory browse dialog opens for that project

### Requirement: Project header context menu
Right-clicking on a project header row SHALL open a project-level context menu. The menu SHALL include a Memory submenu and standard project actions (New Worktree, Team Chat, Team Settings, Initialize wt-control).

#### Scenario: Right-click on project header
- **WHEN** user right-clicks on a project header row
- **THEN** a context menu appears with project-level actions including Memory submenu

#### Scenario: Header row no longer ignored
- **WHEN** user right-clicks on a project header row
- **THEN** the click is NOT silently ignored (current behavior returns early)

### Requirement: Memory submenu in project header context menu
The Memory submenu SHALL show: a disabled status line ("Status: available (N memories)" or "Status: not installed"), a "Browse Memories..." action opening the browse dialog, and a "Remember Note..." action opening the remember dialog. When SKILL.md files lack memory hooks, an additional warning line "OpenSpec skills not hooked" SHALL appear.

#### Scenario: Memory submenu with available shodh-memory
- **WHEN** user opens Memory submenu and shodh-memory is available
- **THEN** status shows "available (N memories)", Browse and Remember actions are enabled

#### Scenario: Memory submenu without shodh-memory
- **WHEN** user opens Memory submenu and shodh-memory is not installed
- **THEN** status shows "not installed", Browse and Remember actions are disabled

#### Scenario: SKILL.md hook warning
- **WHEN** user opens Memory submenu and no SKILL.md file in the project's main repo `.claude/skills/openspec-*/SKILL.md` contains "set-memory"
- **THEN** a disabled warning line "OpenSpec skills not hooked" appears in the submenu

### Requirement: Memory browse dialog
The browse dialog SHALL have two modes: **list mode** (initial) showing all memories, and **search mode** (when query entered) showing semantic recall results. List mode SHALL use `set-memory list --project X` to fetch all memories. Search mode SHALL use `set-memory recall --project X "query"` for semantic search. The dialog SHALL use `WindowStaysOnTopHint` per project conventions.

#### Scenario: Initial load shows all memories
- **WHEN** user opens browse dialog and project has memories
- **THEN** all memories are listed (via `set-memory list`) with content preview, type badge, tags, and date

#### Scenario: Search filters by semantic recall
- **WHEN** user enters a query in the search field and presses Enter
- **THEN** results switch to semantic recall results (via `set-memory recall`)

#### Scenario: Clear search returns to full list
- **WHEN** user clears the search field
- **THEN** display returns to showing all memories (list mode)

#### Scenario: Browse empty project
- **WHEN** user opens browse dialog and project has no memories
- **THEN** dialog shows "No memories yet" with explanation

### Requirement: Remember note dialog
The remember dialog SHALL allow the user to type a note, select a memory type (Learning, Decision, Observation, Event), and optionally add comma-separated tags. On submit, it SHALL save via `set-memory remember` with the project context.

#### Scenario: Save a manual note
- **WHEN** user types content, selects type "Learning", and clicks Save
- **THEN** the note is saved to the project's memory storage with the given type and tags

#### Scenario: Cancel without saving
- **WHEN** user clicks Cancel in the remember dialog
- **THEN** no memory is saved and the dialog closes

## ADDED Requirements

### Requirement: CLI context command
`set-memory context` SHALL call `context_summary()` on the shodh-memory API and output the result as JSON. It SHALL accept `--project` (global flag) and follow the same graceful degradation pattern as other commands.

#### Scenario: Context summary output
- **WHEN** user runs `set-memory context`
- **THEN** output is a JSON object with category keys (decisions, learnings, context) containing recent items per category

#### Scenario: Shodh-memory not installed
- **WHEN** shodh-memory is not installed and user runs `set-memory context`
- **THEN** output is `{}`
- **AND** exit code is 0

### Requirement: Browse dialog default view is context summary
The MemoryBrowseDialog SHALL open in "summary mode" showing the output of `context_summary()` grouped by type, instead of loading all memories.

#### Scenario: Dialog opens with summary
- **WHEN** user opens the Memory Browse dialog for a project
- **THEN** the dialog shows a context summary with sections for Decisions, Learnings, and Context
- **AND** each section shows at most 5 recent items
- **AND** the dialog opens without noticeable delay

#### Scenario: Summary with no memories
- **WHEN** user opens the dialog for a project with no memories
- **THEN** the dialog shows "No memories yet." in the summary view

### Requirement: Toggle between summary and list views
The dialog SHALL have a "Show All" button (in summary mode) and "Summary" button (in list mode) to toggle views.

#### Scenario: Switch to list mode
- **WHEN** user is in summary mode and clicks "Show All"
- **THEN** the dialog switches to paginated list view (first 50 memories)

#### Scenario: Switch back to summary
- **WHEN** user is in list mode and clicks "Summary"
- **THEN** the dialog switches back to context summary view

### Requirement: Search overrides both views
When the user types a search query and presses Enter, the dialog SHALL show recall results as cards, regardless of the current view mode.

#### Scenario: Search from summary mode
- **WHEN** user is in summary mode and searches "flock fix"
- **THEN** the dialog shows recall results as memory cards (up to 20)
- **AND** the search can be cleared to return to summary mode

#### Scenario: Search from list mode
- **WHEN** user is in list mode and searches "flock fix"
- **THEN** the dialog shows recall results as memory cards

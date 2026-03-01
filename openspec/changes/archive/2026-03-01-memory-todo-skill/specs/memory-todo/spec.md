## ADDED Requirements

### Requirement: Quick todo capture
The `/wt:todo <text>` command SHALL save the provided text to shodh-memory as a todo item without asking any questions. It SHALL use type `Context`, tags `todo,backlog`, and auto-detect the current change name (if any) to add a `change:<name>` tag. It SHALL confirm with a single line and the agent SHALL continue with its current work without pursuing the todo content.

#### Scenario: Save a todo during work
- **WHEN** the user types `/wt:todo add dark mode support`
- **THEN** the command saves "add dark mode support" to memory with tags `todo,backlog`
- **AND** outputs `[Todo saved: "add dark mode support"]`
- **AND** the agent continues with whatever it was doing before

#### Scenario: Save a todo with active change context
- **WHEN** the user types `/wt:todo refactor the import logic` while working on change `memory-export-import`
- **THEN** the command saves with tags `todo,backlog,change:memory-export-import`

#### Scenario: Save a todo without active change
- **WHEN** the user types `/wt:todo explore websocket support` with no active change
- **THEN** the command saves with tags `todo,backlog` (no change tag)

#### Scenario: No text provided
- **WHEN** the user types `/wt:todo` with no arguments
- **THEN** the command uses AskUserQuestion to ask what they want to save

### Requirement: List open todos
The `/wt:todo list` subcommand SHALL retrieve all memories tagged with `todo` using tag-based recall and display them in a readable format with their IDs (for use with `done`).

#### Scenario: List with todos present
- **WHEN** the user types `/wt:todo list`
- **AND** 5 todo memories exist
- **THEN** output shows each todo with its ID, content, and creation date

#### Scenario: List with no todos
- **WHEN** the user types `/wt:todo list`
- **AND** no memories are tagged with `todo`
- **THEN** output shows "No open todos."

### Requirement: Mark todo as done
The `/wt:todo done <id>` subcommand SHALL delete the specified memory by ID. It SHALL confirm the deletion.

#### Scenario: Complete a todo
- **WHEN** the user types `/wt:todo done abc123`
- **THEN** the memory with id `abc123` is deleted via `wt-memory forget abc123`
- **AND** output shows `[Todo done: "<content preview>"]`

#### Scenario: Invalid todo ID
- **WHEN** the user types `/wt:todo done nonexistent`
- **THEN** output shows an error that the todo was not found

### Requirement: Graceful degradation
If shodh-memory is not available, the command SHALL inform the user and exit without error.

#### Scenario: Memory system unavailable
- **WHEN** the user types `/wt:todo something`
- **AND** `wt-memory health` fails
- **THEN** output shows "Memory system not available."

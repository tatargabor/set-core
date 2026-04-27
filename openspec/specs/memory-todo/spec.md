# Memory Todo Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Todo add command
`set-memory todo add <text>` SHALL save the provided text as a memory with `experience_type=Context`, tags `todo,backlog`, and metadata `{todo_status: "open"}`. If an active OpenSpec change is detected, a `change:<name>` tag SHALL be added automatically. The command SHALL print a confirmation line and exit.

#### Scenario: Add a todo
- **WHEN** user runs `echo "refactor auth module" | set-memory todo add --tags priority:high`
- **THEN** a memory is saved with content "refactor auth module", tags `todo,backlog,priority:high`, metadata `{todo_status: "open"}`
- **AND** stdout prints `Todo saved: "refactor auth module"`

#### Scenario: Add a todo with active change context
- **WHEN** user runs `echo "fix edge case" | set-memory todo add`
- **AND** an OpenSpec change `shodh-memory-upgrade` is active
- **THEN** the memory is saved with tags `todo,backlog,change:shodh-memory-upgrade`

#### Scenario: Add with empty input
- **WHEN** user runs `set-memory todo add` with empty stdin
- **THEN** the command exits with non-zero code
- **AND** stderr prints "No todo text provided"

### Requirement: Todo list command
`set-memory todo list` SHALL retrieve all memories tagged with `todo` where metadata `todo_status` is `open` (or absent) and display them with ID, content preview, tags, and creation date.

#### Scenario: List with open todos
- **WHEN** user runs `set-memory todo list`
- **AND** 3 todo memories exist
- **THEN** stdout prints each todo with its ID (truncated to 8 chars), content, tags, and date
- **AND** output is formatted as a readable list

#### Scenario: List with no todos
- **WHEN** user runs `set-memory todo list`
- **AND** no memories are tagged with `todo`
- **THEN** stdout prints "No open todos."

#### Scenario: List as JSON
- **WHEN** user runs `set-memory todo list --json`
- **THEN** stdout prints the full JSON array of todo memories

### Requirement: Todo done command
`set-memory todo done <id>` SHALL delete the specified todo memory by ID using `forget()`. The command SHALL confirm the deletion with a content preview.

#### Scenario: Complete a todo
- **WHEN** user runs `set-memory todo done abc12345`
- **AND** a todo memory with that ID prefix exists
- **THEN** the memory is deleted
- **AND** stdout prints `Todo done: "refactor auth module"`

#### Scenario: Complete with ID prefix
- **WHEN** user runs `set-memory todo done abc1`
- **AND** exactly one todo memory ID starts with `abc1`
- **THEN** the matching memory is deleted

#### Scenario: Invalid todo ID
- **WHEN** user runs `set-memory todo done nonexistent`
- **THEN** stderr prints "Todo not found: nonexistent"
- **AND** the command exits with non-zero code

### Requirement: Todo clear command
`set-memory todo clear` SHALL delete all memories tagged with `todo`. It SHALL require `--confirm` flag.

#### Scenario: Clear all todos with confirmation
- **WHEN** user runs `set-memory todo clear --confirm`
- **THEN** all memories tagged with `todo` are deleted via `forget_by_tags(["todo"])`
- **AND** stdout prints `Cleared N todos.`

#### Scenario: Clear without confirmation
- **WHEN** user runs `set-memory todo clear` (without `--confirm`)
- **THEN** the command exits with non-zero code
- **AND** stderr prints "Use --confirm to clear all todos"

### Requirement: Todo slash command
The `/wt:todo` slash command (`.claude/commands/wt/todo.md`) SHALL route to `set-memory todo` subcommands. It SHALL instruct the agent to NOT pursue or discuss the todo content after saving — just confirm and continue with current work.

#### Scenario: Fire-and-forget save
- **WHEN** user types `/wt:todo add dark mode support`
- **THEN** the agent runs `echo "add dark mode support" | set-memory todo add`
- **AND** confirms with one line
- **AND** continues with whatever it was doing before

#### Scenario: List todos
- **WHEN** user types `/wt:todo list`
- **THEN** the agent runs `set-memory todo list` and displays the results

#### Scenario: Complete a todo
- **WHEN** user types `/wt:todo done abc1`
- **THEN** the agent runs `set-memory todo done abc1` and confirms

### Requirement: Todo MCP tools
The memory MCP server SHALL expose `add_todo(content, tags)`, `list_todos()`, and `complete_todo(id)` tools that call the corresponding `set-memory todo` CLI subcommands.

#### Scenario: MCP add_todo
- **WHEN** agent calls MCP tool `add_todo(content="fix auth bug", tags="priority:high")`
- **THEN** the tool runs `echo "fix auth bug" | set-memory todo add --tags priority:high`
- **AND** returns the confirmation message

#### Scenario: MCP list_todos
- **WHEN** agent calls MCP tool `list_todos()`
- **THEN** the tool runs `set-memory todo list --json`
- **AND** returns the JSON array

#### Scenario: MCP complete_todo
- **WHEN** agent calls MCP tool `complete_todo(id="abc12345")`
- **THEN** the tool runs `set-memory todo done abc12345`
- **AND** returns the confirmation message

### Requirement: Graceful degradation
All todo commands SHALL exit silently with code 0 when shodh-memory is not installed, consistent with existing set-memory commands.

#### Scenario: Todo with shodh-memory unavailable
- **WHEN** shodh-memory is not installed
- **AND** user runs `set-memory todo list`
- **THEN** the command exits 0
- **AND** stdout prints "No open todos." (not an error)

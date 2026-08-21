## MODIFIED Requirements

### Requirement: Help command covers CLI tools
The help command SHALL list the framework's CLI tools with a one-line description for each,
and SHALL NOT list a command the framework no longer installs.

#### Scenario: CLI tools listed
- **WHEN** the help command content is loaded
- **THEN** it SHALL contain a "CLI Commands" section listing at minimum: `set-new`, `set-list`, `set-work`, `set-close`, `set-merge`, `set-status`, `set-loop`, `set-control`, `set-project`, `set-usage`, `set-config`
- **AND** it SHALL NOT list `set-memory` or `set-memoryd`

#### Scenario: Each CLI tool has description
- **WHEN** a CLI tool is listed in the help command
- **THEN** it SHALL have a one-line description of what it does

## REMOVED Requirements

### Requirement: Help command covers MCP tools
**Reason**: The requirement named the memory MCP tools explicitly — `remember`, `recall`,
`proactive_context`, `forget`, `list_memories`, `brain`, `context_summary` — and sourced
them from `set-memory`. All twenty-seven memory tools are removed, so a requirement to
advertise them would document a surface that does not exist.

**Migration**: Replaced by "Help command covers the registered MCP tools" below, which is
tied to what the server actually registers rather than to a hard-coded list.

## ADDED Requirements

### Requirement: Help command covers the registered MCP tools
The help command SHALL list the MCP tools the server actually registers, with a one-line
description for each, and SHALL name no tool the server does not register.

#### Scenario: Worktree and team MCP tools listed
- **WHEN** the help command content is loaded
- **THEN** it SHALL list at minimum: `list_worktrees`, `get_activity`, `get_team_status`, `send_message`, `get_inbox`

#### Scenario: No memory MCP tool is advertised
- **WHEN** the help command content is loaded
- **THEN** it SHALL name none of `remember`, `recall`, `proactive_context`, `forget`, `list_memories`, `brain`, `context_summary`, `add_todo`, `list_todos`, `complete_todo`

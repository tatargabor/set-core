## ADDED Requirements

### Requirement: /wt:memory slash command
A `/wt:memory` slash command SHALL be available via `.claude/commands/wt/memory.md`. The command SHALL support subcommands: `status`, `list`, `recall`, `remember`, and `browse`.

#### Scenario: Memory status
- **WHEN** agent runs `/wt:memory status`
- **THEN** the agent runs `set-memory status` and displays the result (health, count, storage path)

#### Scenario: Memory recall
- **WHEN** agent runs `/wt:memory recall <query>`
- **THEN** the agent runs `set-memory recall "<query>" --limit 5` and displays matching memories with their types and tags

#### Scenario: Memory remember
- **WHEN** agent runs `/wt:memory remember <content>`
- **THEN** the agent prompts for memory type (Decision, Learning, Observation, Event) and optional tags, then runs `echo "<content>" | set-memory remember --type <type> --tags <tags>`

#### Scenario: Memory list
- **WHEN** agent runs `/wt:memory list`
- **THEN** the agent runs `set-memory list` and displays all memories for the current project in a readable format

#### Scenario: Memory browse
- **WHEN** agent runs `/wt:memory browse` or `/wt:memory` with no arguments
- **THEN** the agent runs `set-memory status` followed by `set-memory list`, showing a summary of all memories grouped by type

#### Scenario: Memory unavailable
- **WHEN** agent runs any `/wt:memory` subcommand and `set-memory health` fails
- **THEN** the agent displays "Memory system not available — shodh-memory is not running" and suggests checking with `set-memory health`

## ADDED Requirements

### Requirement: MCP server exposes todo tools
The memory MCP server (`set-memory-mcp-server.py`) SHALL expose todo management tools.

#### Scenario: add_todo tool
- **WHEN** agent calls `add_todo(content="fix auth bug", tags="priority:high")`
- **THEN** the tool runs `echo "fix auth bug" | set-memory todo add --tags priority:high`
- **AND** returns the confirmation string

#### Scenario: list_todos tool
- **WHEN** agent calls `list_todos()`
- **THEN** the tool runs `set-memory todo list --json`
- **AND** returns the JSON array of open todos

#### Scenario: complete_todo tool
- **WHEN** agent calls `complete_todo(id="abc12345")`
- **THEN** the tool runs `set-memory todo done abc12345`
- **AND** returns the confirmation string

### Requirement: MCP server exposes API parity tools
The memory MCP server SHALL expose tools for the newly wrapped shodh-memory methods.

#### Scenario: verify_index tool
- **WHEN** agent calls `verify_index()`
- **THEN** the tool runs `set-memory verify`
- **AND** returns the JSON result

#### Scenario: consolidation_report tool
- **WHEN** agent calls `consolidation_report(since=None)`
- **THEN** the tool runs `set-memory consolidation [--since <date>]`
- **AND** returns the JSON result

#### Scenario: graph_stats tool
- **WHEN** agent calls `graph_stats()`
- **THEN** the tool runs `set-memory graph-stats`
- **AND** returns the JSON result

#### Scenario: recall_by_date tool
- **WHEN** agent calls `recall_by_date(since="2026-02-01", until="2026-02-15")`
- **THEN** the tool runs `set-memory recall --since 2026-02-01 --until 2026-02-15`
- **AND** returns the JSON array

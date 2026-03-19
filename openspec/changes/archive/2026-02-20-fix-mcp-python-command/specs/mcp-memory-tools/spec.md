## MODIFIED Requirements

### Requirement: Own MCP server wrapping full set-memory CLI
A Python MCP server (`bin/set-memory-mcp-server.py`) SHALL expose the full `set-memory` CLI as MCP tools. It SHALL shell out to `set-memory` commands, ensuring all custom logic (branch boosting, auto-tagging, dedup, sync) applies to MCP calls.

#### Scenario: MCP server registration
- **WHEN** `set-project init` runs on a project
- **THEN** it SHALL register the MCP server via `claude mcp add set-memory -- <path>/set-memory-mcp-server.py` (no explicit python interpreter)
- **AND** the server SHALL use stdio transport (standard MCP protocol)
- **AND** the script SHALL be executed directly via its `#!/usr/bin/env python3` shebang

#### Scenario: MCP server re-registration on init
- **WHEN** `set-project init` runs and set-memory MCP is already registered
- **THEN** it SHALL re-register (overwrite) to ensure the command is correct
- **AND** this SHALL fix any stale `"command": "python"` entries from previous installs

#### Scenario: LLM can use memory tools
- **WHEN** Claude Code starts a session with the MCP server active
- **THEN** the LLM SHALL have access to ~20 tools covering the full set-memory interface
- **AND** these tools SHALL operate through the same `set-memory` CLI path as hooks

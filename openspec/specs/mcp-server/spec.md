# mcp-server Specification

## Purpose
TBD - created by archiving change mcp-server-documentation. Update Purpose after archive.
## Requirements
### Requirement: MCP server exposes set-core state
The system SHALL provide an MCP server (`wt_mcp_server.py`) that exposes set-core state through the Model Context Protocol.

#### Scenario: Server starts successfully
- **WHEN** Claude Code starts with set-core MCP configured
- **THEN** the MCP server connects via stdio transport
- **AND** server reports "Connected" status in `claude mcp list`

#### Scenario: Server available globally
- **WHEN** MCP server is configured with `--scope user`
- **THEN** the server is accessible from any project directory
- **AND** configuration is stored in `~/.claude.json`

### Requirement: MCP server uses FastMCP framework
The system SHALL use FastMCP Python framework for MCP server implementation.

#### Scenario: Tool definition with decorators
- **WHEN** developer defines a new MCP tool
- **THEN** tool is defined using `@mcp.tool` decorator
- **AND** no boilerplate JSON-RPC handling is required

### Requirement: MCP server is read-only
The system SHALL NOT expose any write operations through MCP. All MCP tools MUST be read-only state queries.

#### Scenario: No action tools in MCP
- **WHEN** agent queries available MCP tools
- **THEN** no tools modify worktrees, start/stop Ralph, or change any state
- **AND** all write operations remain in wt skill (wt-new, wt-close, wt-loop start)

### Requirement: MCP reads from file-based state
The system SHALL read state from JSON files rather than executing CLI commands.

#### Scenario: Ralph status from file
- **WHEN** agent calls `get_ralph_status()`
- **THEN** MCP reads `<wt-path>/.claude/loop-state.json` directly
- **AND** does NOT spawn `wt-loop status` subprocess

#### Scenario: Projects from config file
- **WHEN** MCP needs project list
- **THEN** reads from `~/.config/set-core/projects.json`
- **AND** does NOT call `wt-list` command


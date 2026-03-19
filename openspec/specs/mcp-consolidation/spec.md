## Requirements

### Requirement: Unified MCP server serves both worktree and memory tools
The `mcp-server/set_mcp_server.py` SHALL expose all memory tools alongside existing worktree/team tools in a single FastMCP server instance.

#### Scenario: Server exposes memory tools
- **WHEN** the MCP server starts
- **THEN** it SHALL register all memory tools (remember, recall, forget, list_memories, get_memory, proactive_context, context_summary, brain, memory_stats, health, audit, cleanup, dedup, sync, sync_push, sync_pull, sync_status, export_memories, import_memories, add_todo, list_todos, complete_todo, verify_index, consolidation_report, graph_stats, recall_by_date, forget_by_tags)
- **AND** it SHALL register all existing worktree/team tools (list_worktrees, get_ralph_status, get_worktree_tasks, get_team_status, get_activity, send_message, get_inbox)

#### Scenario: Memory tools use project-scoped CWD
- **WHEN** a memory tool is invoked
- **THEN** the subprocess call to `set-memory` SHALL use `cwd=os.environ.get("CLAUDE_PROJECT_DIR")`
- **AND** `set-memory`'s `resolve_project()` SHALL detect the correct git project from that CWD

#### Scenario: Worktree tools unaffected
- **WHEN** a worktree or team tool is invoked
- **THEN** it SHALL continue to use `projects.json` for project discovery
- **AND** it SHALL NOT depend on `CLAUDE_PROJECT_DIR`

### Requirement: CLAUDE_PROJECT_DIR env var propagation
The MCP server registration command SHALL include `CLAUDE_PROJECT_DIR` set to the project root path.

#### Scenario: Registration command includes env var
- **WHEN** `set-project init` registers the MCP server
- **THEN** the registration command SHALL be: `env CLAUDE_PROJECT_DIR="<project-path>" uv --directory "<mcp-server-dir>" run python set_mcp_server.py`

#### Scenario: env var available at runtime
- **WHEN** the MCP server process starts
- **THEN** `os.environ["CLAUDE_PROJECT_DIR"]` SHALL contain the absolute path to the project root

### Requirement: Standalone set-memory MCP server removed
The `bin/set-memory-mcp-server.py` file SHALL be deleted.

#### Scenario: File removed from repository
- **WHEN** this change is applied
- **THEN** `bin/set-memory-mcp-server.py` SHALL NOT exist
- **AND** no code SHALL reference it

### Requirement: Legacy set-memory MCP registration cleaned up
Registration flows SHALL remove any existing `set-memory` MCP server registration.

#### Scenario: set-project init cleans up legacy registration
- **WHEN** `set-project init` runs
- **THEN** it SHALL run `claude mcp remove set-memory` before registering the unified server
- **AND** it SHALL register the unified server as `set-core`

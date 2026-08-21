## REMOVED Requirements

### Requirement: Unified MCP server serves both worktree and memory tools
**Reason**: The memory subsystem this requirement consolidated is removed. Twenty-seven of
the server's thirty-five tools shelled out to `set-memory`, a command the framework no
longer installs; keeping them registered would expose tools that fail on every call.

**Migration**: None. There is no replacement tool. Durable knowledge lives in the runtime's
native per-repository memory directory, which a session reads with ordinary file tools —
see the `native-memory-layer` capability. The `add_todo` / `list_todos` / `complete_todo`
trio is dropped with the store that backed it; any open todo is preserved in the archive
taken before the removal.

## ADDED Requirements

### Requirement: The MCP server exposes worktree and team tools only
The `mcp-server/set_mcp_server.py` SHALL expose worktree and team tools, and SHALL NOT
register any tool that invokes a command the framework does not install.

#### Scenario: Server exposes exactly the surviving tools
- **WHEN** the MCP server starts
- **THEN** it SHALL register exactly: `run_command`, `list_worktrees`, `get_ralph_status`, `get_worktree_tasks`, `get_team_status`, `get_activity`, `send_message`, `get_inbox`

#### Scenario: No memory tool is registered
- **WHEN** the MCP server's registered tool names are enumerated
- **THEN** none SHALL be among `remember`, `recall`, `recall_by_date`, `proactive_context`, `forget`, `forget_by_tags`, `list_memories`, `get_memory`, `context_summary`, `brain`, `memory_stats`, `memory_health`, `audit`, `cleanup`, `dedup`, `verify_index`, `consolidation_report`, `graph_stats`, `sync`, `sync_push`, `sync_pull`, `sync_status`, `export_memories`, `import_memories`, `add_todo`, `list_todos`, `complete_todo`

#### Scenario: No tool shells out to a removed command
- **WHEN** the server source is scanned for subprocess invocations
- **THEN** no tool SHALL invoke `set-memory` or `set-memoryd`

#### Scenario: Worktree tools unaffected
- **WHEN** a worktree or team tool is invoked
- **THEN** it SHALL continue to use `projects.json` for project discovery
- **AND** it SHALL NOT depend on `CLAUDE_PROJECT_DIR`

## ADDED Requirements

### Requirement: Own MCP server wrapping full set-memory CLI
A Python MCP server (`bin/set-memory-mcp-server.py`) SHALL expose the full `set-memory` CLI as MCP tools. It SHALL shell out to `set-memory` commands, ensuring all custom logic (branch boosting, auto-tagging, dedup, sync) applies to MCP calls.

#### Scenario: MCP server registration
- **WHEN** `set-project init` runs on a project
- **THEN** it SHALL register the MCP server via `claude mcp add set-memory -- python <path>/set-memory-mcp-server.py`
- **AND** the server SHALL use stdio transport (standard MCP protocol)

#### Scenario: MCP server already registered
- **WHEN** `set-project init` runs and set-memory MCP is already registered
- **THEN** it SHALL NOT duplicate the registration

#### Scenario: LLM can use memory tools
- **WHEN** Claude Code starts a session with the MCP server active
- **THEN** the LLM SHALL have access to ~20 tools covering the full set-memory interface
- **AND** these tools SHALL operate through the same `set-memory` CLI path as hooks

### Requirement: Core memory tools
The MCP server SHALL expose core memory operations as tools.

#### Scenario: remember tool
- **WHEN** the LLM calls `remember(content, type, tags)`
- **THEN** the server SHALL execute `echo <content> | set-memory remember --type <type> --tags <tags>`
- **AND** SHALL return the result (memory ID or error)

#### Scenario: recall tool
- **WHEN** the LLM calls `recall(query, limit, mode, tags)`
- **THEN** the server SHALL execute `set-memory recall "<query>" --limit <limit> --mode <mode> --tags <tags>`
- **AND** SHALL return the JSON result array

#### Scenario: proactive_context tool
- **WHEN** the LLM calls `proactive_context(context, limit)`
- **THEN** the server SHALL execute `set-memory proactive "<context>" --limit <limit>`
- **AND** SHALL return the JSON result array with relevance scores

#### Scenario: forget tool
- **WHEN** the LLM calls `forget(id)`
- **THEN** the server SHALL execute `set-memory forget <id>`

#### Scenario: forget_by_tags tool
- **WHEN** the LLM calls `forget_by_tags(tags)`
- **THEN** the server SHALL execute `set-memory forget --tags <tags>`

#### Scenario: list_memories tool
- **WHEN** the LLM calls `list_memories(type, limit)`
- **THEN** the server SHALL execute `set-memory list --type <type> --limit <limit>`

#### Scenario: get_memory tool
- **WHEN** the LLM calls `get_memory(id)`
- **THEN** the server SHALL execute `set-memory get <id>`

#### Scenario: context_summary tool
- **WHEN** the LLM calls `context_summary(topic)`
- **THEN** the server SHALL execute `set-memory context <topic>`

#### Scenario: brain tool
- **WHEN** the LLM calls `brain()`
- **THEN** the server SHALL execute `set-memory brain`

#### Scenario: memory_stats tool
- **WHEN** the LLM calls `memory_stats()`
- **THEN** the server SHALL execute `set-memory stats --json`

### Requirement: Maintenance tools
The MCP server SHALL expose memory maintenance operations.

#### Scenario: health tool
- **WHEN** the LLM calls `health()`
- **THEN** the server SHALL execute `set-memory health`

#### Scenario: audit tool
- **WHEN** the LLM calls `audit(threshold)`
- **THEN** the server SHALL execute `set-memory audit --threshold <threshold> --json`

#### Scenario: cleanup tool
- **WHEN** the LLM calls `cleanup(threshold, dry_run)`
- **THEN** the server SHALL execute `set-memory cleanup --threshold <threshold>` with optional `--dry-run`

#### Scenario: dedup tool
- **WHEN** the LLM calls `dedup(threshold, dry_run)`
- **THEN** the server SHALL execute `set-memory dedup --threshold <threshold>` with optional `--dry-run`

### Requirement: Sync tools
The MCP server SHALL expose git-based memory sync operations.

#### Scenario: sync tool
- **WHEN** the LLM calls `sync()`
- **THEN** the server SHALL execute `set-memory sync`

#### Scenario: sync_push tool
- **WHEN** the LLM calls `sync_push()`
- **THEN** the server SHALL execute `set-memory sync push`

#### Scenario: sync_pull tool
- **WHEN** the LLM calls `sync_pull(from_source)`
- **THEN** the server SHALL execute `set-memory sync pull --from <from_source>`

#### Scenario: sync_status tool
- **WHEN** the LLM calls `sync_status()`
- **THEN** the server SHALL execute `set-memory sync status`

### Requirement: Export/Import tools
The MCP server SHALL expose memory export and import operations.

#### Scenario: export tool
- **WHEN** the LLM calls `export_memories()`
- **THEN** the server SHALL execute `set-memory export` and return the JSON

#### Scenario: import_memories tool
- **WHEN** the LLM calls `import_memories(file_path, dry_run)`
- **THEN** the server SHALL execute `set-memory import <file_path>` with optional `--dry-run`

### Requirement: CLAUDE.md documents MCP tools alongside hooks
The CLAUDE.md Persistent Memory section SHALL document both automatic (hooks) and active (MCP) memory access.

#### Scenario: CLAUDE.md content
- **WHEN** a project's CLAUDE.md is deployed
- **THEN** it SHALL explain that memory context is injected automatically via system-reminders
- **AND** SHALL explain that MCP tools are available for deeper memory interactions
- **AND** SHALL list the key MCP tool names: remember, recall, proactive_context

### Requirement: Hooks and MCP share the same path
Both the hook system (via `set-memory` CLI) and the MCP server (via `set-memory` CLI) SHALL use the identical code path, ensuring branch boosting, auto-tagging, and all custom logic applies to both.

#### Scenario: Memory saved via hook, recalled via MCP
- **WHEN** the Stop hook saves a memory via `set-memory remember`
- **AND** the LLM later calls the MCP `recall` tool
- **THEN** the saved memory SHALL be findable via MCP recall

#### Scenario: Memory saved via MCP, surfaced via hook
- **WHEN** the LLM calls the MCP `remember` tool to save an insight
- **AND** a subsequent hook fires and recalls memory
- **THEN** the MCP-saved memory SHALL be surfaceable via hook injection

#### Scenario: Branch boosting works in both paths
- **WHEN** the LLM calls MCP `recall` while on branch `feature-x`
- **THEN** branch boosting SHALL apply (dual-query: branch-filtered + unfiltered)
- **AND** the behavior SHALL be identical to hook-initiated recall

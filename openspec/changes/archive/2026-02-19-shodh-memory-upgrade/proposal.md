## Why

shodh-memory 0.1.81 is out (we're on 0.1.75) with new index maintenance methods. Additionally, several Python SDK methods are not wrapped in `set-memory` CLI or exposed via MCP (recall_by_date, forget_by_date, consolidation_report, consolidation_events, graph_stats, verify_index, flush). The upstream MCP server has a full todo system but the Python SDK doesn't expose it — we need our own todo implementation built on the existing memory API for quick idea/task capture during development sessions.

## What Changes

- **Version upgrade**: shodh-memory 0.1.75 → 0.1.81 (pyproject.toml pin update)
- **New CLI subcommands in `set-memory`**: `verify`, `recall-by-date`, `forget-by-date`, `consolidation`, `graph-stats`, `flush`
- **New MCP tools**: All new CLI subcommands exposed via `set-memory-mcp-server.py`
- **Todo system**: `set-memory todo` subcommand with add/list/done/clear operations, built on top of existing remember/recall_by_tags/forget API using `todo` tag convention
- **Todo MCP tools**: `add_todo`, `list_todos`, `complete_todo` exposed via MCP server
- **Todo slash command**: `/wt:todo` for fire-and-forget idea capture during agent sessions

## Capabilities

### New Capabilities
- `memory-todo`: Todo/task management built on shodh-memory using tag conventions (todo, priority, status metadata). CLI subcommand + MCP tools + slash command.
- `shodh-api-parity`: Wrapping all remaining shodh-memory Python SDK methods not yet exposed in set-memory CLI and MCP server (verify_index, recall_by_date, forget_by_date, consolidation_report, consolidation_events, graph_stats, flush).

### Modified Capabilities
- `memory-cli`: Adding new subcommands (todo, verify, recall-by-date, forget-by-date, consolidation, graph-stats, flush)
- `mcp-server`: Exposing new tools for API parity methods and todo operations
- `shodh-cli-upgrade`: Version pin update from 0.1.75 to 0.1.81

## Impact

- **`bin/set-memory`**: New subcommands (~200 lines)
- **`bin/set-memory-mcp-server.py`**: New MCP tool registrations (~80 lines)
- **`.claude/commands/wt/todo.md`**: New slash command
- **`pyproject.toml`**: Version pin bump
- **No breaking changes**: Purely additive

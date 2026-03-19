## Why

Two separate MCP servers (`set-core` and `set-memory`) run from the same `mcp-server/` venv but are registered independently. After the macOS Python fix (a6e5209), `set-memory` MCP was moved to `uv --directory mcp-server/`, making its CWD `mcp-server/` instead of the project root. This breaks `set-memory`'s `resolve_project()` (which relies on git toplevel detection), causing all MCP memory calls to hit the `_global` storage instead of the project-specific one. Additionally, running two MCP server processes from the same venv is unnecessary overhead.

## What Changes

- **Merge memory tools into the unified `wt_mcp_server.py`**: All `set-memory` MCP tools (remember, recall, forget, stats, cleanup, etc.) move into the existing set-core MCP server
- **Per-project registration with `CLAUDE_PROJECT_DIR` env var**: The MCP server receives the project path at registration time, and passes it as `cwd=` to all `set-memory` subprocess calls
- **Single registration point in `set-project init`**: Replace the dual registration (global `set-core` in install.sh + per-project `set-memory` in set-project) with one per-project `set-core` registration
- **Remove `bin/set-memory-mcp-server.py`**: No longer needed after merge
- **Remove global MCP registration from `install.sh`**: Per-project registration via `set-project init` becomes the only path
- **Garbage memory cleanup**: Add a one-time cleanup command/documentation for the existing corrupted memories (short fragments, `\x01` prefix entries)

## Capabilities

### New Capabilities
- `mcp-consolidation`: Unified MCP server architecture with project-context propagation

### Modified Capabilities
- `mcp-memory-tools`: Memory MCP tools move from standalone server to unified server, gaining correct project context via `CLAUDE_PROJECT_DIR`
- `project-init-deploy`: Single MCP registration replacing dual registration

## Impact

- **`mcp-server/wt_mcp_server.py`**: Gains ~30 memory tool functions (shell-out to `set-memory` CLI)
- **`bin/set-project`**: `_register_mcp_server()` updated — registers `set-core` instead of `set-memory`, adds `CLAUDE_PROJECT_DIR` env var
- **`bin/set-memory-mcp-server.py`**: Deleted
- **`install.sh`**: Global MCP registration removed (lines ~708-714)
- **Cross-platform**: Must work on both Linux and macOS (uv + env var propagation)

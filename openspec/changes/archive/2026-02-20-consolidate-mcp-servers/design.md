## Context

set-core currently runs two separate MCP servers from the same `mcp-server/` venv:

1. **set-core** (`mcp-server/wt_mcp_server.py`): Registered globally (`--scope user`) in `install.sh`. Provides worktree, Ralph, team, and messaging tools. Uses `projects.json` for project discovery — does not depend on CWD.

2. **set-memory** (`bin/set-memory-mcp-server.py`): Registered per-project in `set-project init`. Shells out to `set-memory` CLI. After macOS fix (a6e5209), runs via `uv --directory mcp-server/`, which sets CWD to `mcp-server/` — a non-git directory. This breaks `resolve_project()` → all memory calls hit `_global` storage instead of project-specific storage.

Both use the same `pyproject.toml` and `fastmcp` dependency. Running two server processes is unnecessary.

## Goals / Non-Goals

**Goals:**
- One MCP server process (`set-core`) serving all tools (worktree + memory)
- Correct project context for memory tools via `CLAUDE_PROJECT_DIR` env var
- Cross-platform (Linux + macOS) — env var propagation must work with both `env` command syntax and `uv`
- Single registration point (`set-project init`)
- Remove standalone `set-memory-mcp-server.py`

**Non-Goals:**
- Changing the memory tools' shell-out architecture (still calls `set-memory` CLI)
- Changing how set-core tools work (still reads `projects.json`)
- Cleaning up existing garbage memories (separate task, not part of this change)
- Changing hook behavior

## Decisions

### Decision 1: Merge direction — memory tools into wt_mcp_server.py

**Choice**: Copy the memory tool functions from `bin/set-memory-mcp-server.py` into `mcp-server/wt_mcp_server.py`.

**Rationale**: `wt_mcp_server.py` is the established server with proper project structure (`mcp-server/pyproject.toml`). The memory server was always a simpler shell-out wrapper. Adding ~100 lines of tool definitions to the existing server is straightforward.

**Alternative rejected**: Creating a third unified server — unnecessary complexity.

### Decision 2: Project context via `CLAUDE_PROJECT_DIR` env var

**Choice**: Bake the project path into the MCP server startup command as an environment variable.

Registration command:
```
claude mcp add set-core -- env CLAUDE_PROJECT_DIR="$reg_path" uv --directory "$mcp_server_dir" run python wt_mcp_server.py
```

In `wt_mcp_server.py`, the memory tools' `_run_memory()` helper passes `cwd=os.environ.get("CLAUDE_PROJECT_DIR")` to `subprocess.run()`.

**Rationale**: Simple, explicit, cross-platform. The `env` command works on both Linux and macOS. No MCP protocol extensions needed.

**Alternative rejected**: Using MCP `roots` capability — Claude Code's MCP implementation doesn't reliably expose workspace roots in a way we can use for subprocess CWD.

### Decision 3: Per-project registration only

**Choice**: Remove the global `--scope user` registration from `install.sh`. All MCP registration happens in `set-project init`.

**Rationale**: Memory tools MUST be project-scoped (different storage per project). The set-core tools (worktree list, Ralph status) are project-agnostic but only useful in set-core-managed projects. Since `set-project init` already runs for every managed project, per-project registration is natural and sufficient.

### Decision 4: MCP server name stays `set-core`

**Choice**: Keep the name `set-core` for the unified server. Remove the `set-memory` server name.

**Rationale**: `set-core` is already registered globally. We just need to update its registration to be per-project with `CLAUDE_PROJECT_DIR`. Tools previously under `set-memory` will now appear under `set-core` — the LLM-facing tool names (`remember`, `recall`, etc.) remain the same.

### Decision 5: env command for cross-platform env var injection

**Choice**: Use `env CLAUDE_PROJECT_DIR="$path"` prefix in the registration command.

**Rationale**: The POSIX `env` command works identically on Linux and macOS. Using shell export or inline `VAR=val` before `uv` would require a shell wrapper.

## Risks / Trade-offs

**[Risk] Existing `set-memory` MCP registrations linger** → `set-project init` SHALL run `claude mcp remove set-memory` before registering the unified server. The `install.sh` SHALL also clean up global set-core registration if present.

**[Risk] `env` command not in PATH on some systems** → Extremely unlikely; `env` is POSIX and present on all Unix-like systems. No mitigation needed.

**[Risk] Per-project registration means MCP not available outside projects** → Acceptable. MCP tools are only useful in set-core-managed projects.

**[Risk] Tool name collision** → The set-core server already has tools like `list_worktrees`. The memory tools (`remember`, `recall`, etc.) have different names. No collision.

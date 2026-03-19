## Context

set-core wraps shodh-memory (Python PyO3 bindings to a Rust memory engine) via `bin/set-memory` CLI and `bin/set-memory-mcp-server.py`. Currently on v0.1.75; v0.1.81 adds `index_health`, `verify_index`, `repair_index`. Several SDK methods remain unwrapped: `recall_by_date`, `forget_by_date`, `consolidation_report`, `consolidation_events`, `graph_stats`, `flush`. The upstream NPM MCP server has 8 todo tools backed by Rust internals, but these aren't exposed in the Python SDK — we build our own.

Existing architecture: `set-memory` CLI uses `run_shodh_python` (inline Python via heredoc) with `_SHODH_*` env vars, serialized by `run_with_lock` (mkdir-based lock). The MCP server shells out to `set-memory` CLI.

## Goals / Non-Goals

**Goals:**
- Upgrade shodh-memory to 0.1.81
- Wrap all remaining Python SDK methods relevant to development memory workflows
- Implement a todo system using the existing remember/recall_by_tags/forget API with tag conventions
- Expose everything via MCP server
- Provide a `/wt:todo` slash command for fire-and-forget capture

**Non-Goals:**
- Wrapping robotics-specific methods (record_obstacle, record_sensor, record_waypoint) — not relevant
- Using the upstream NPM MCP server — would require Node.js dependency and different architecture
- Waiting for Python SDK to expose native todo bindings — timeline unknown
- Priority levels, subtasks, recurring todos — keep it simple (can add later)

## Decisions

### D1: Todo storage via tag convention
**Decision**: Todos are regular memories with `experience_type=Context`, tag `todo`, and metadata fields `{todo_status: "open"|"done", todo_priority: "normal"|"high", todo_due: "<ISO date>"}`.
**Alternatives considered**:
- Separate todo storage: Would require new data path, more complexity
- Using NPM MCP server: Would add Node.js dependency
**Rationale**: Zero new storage infrastructure. Works with existing recall_by_tags, proactive_context, export/import, sync. Todos are just memories you can search semantically.

### D2: `set-memory todo` as CLI subcommand, not separate script
**Decision**: Add `cmd_todo` to `bin/set-memory` with subcommands: `add`, `list`, `done`, `clear`.
**Alternatives considered**:
- Separate `wt-todo` script: More files, duplication
- Slash command only: No CLI access for scripts/hooks
**Rationale**: Follows existing pattern. The `/wt:todo` slash command calls `set-memory todo` just like `/wt:memory` calls `set-memory`.

### D3: Group new API parity methods as subcommands
**Decision**: Add subcommands following existing naming:
- `set-memory verify` → `verify_index()`
- `set-memory recall --since/--until` → `recall_by_date(start, end)`
- `set-memory forget --since/--until` → `forget_by_date(start, end)`
- `set-memory consolidation` → `consolidation_report()` / `consolidation_events()`
- `set-memory graph-stats` → `graph_stats()`
- `set-memory flush` → `flush()`
**Rationale**: Consistent with existing CLI design. Date flags on recall/forget extend existing subcommands rather than creating new ones.

### D4: MCP server exposes todo as read-write tools
**Decision**: The memory MCP server (`set-memory-mcp-server.py`) already has write tools (remember, forget, cleanup, dedup). Add `add_todo`, `list_todos`, `complete_todo`.
**Rationale**: The set-core MCP server (wt_mcp_server.py) is read-only, but the memory MCP server is a separate server that already does writes. Consistent with its existing pattern.

### D5: Version pin update strategy
**Decision**: Change `>=0.1.75,!=0.1.80` to `>=0.1.81` in pyproject.toml.
**Rationale**: 0.1.81 is the minimum for `verify_index`. The `!=0.1.80` exclusion is no longer needed since we're jumping past it.

## Risks / Trade-offs

- **[Risk] Todo memories pollute regular recall**: Tagged memories could surface in unrelated searches.
  → Mitigation: `todo` tag makes them distinguishable. `proactive_context()` relevance scoring filters naturally. Can add `--exclude-tags todo` to recall later if needed.

- **[Risk] No native todo_id — relies on memory ID**: Memory IDs are UUIDs, not human-friendly.
  → Mitigation: `set-memory todo list` shows content preview alongside ID. The slash command handles IDs transparently.

- **[Trade-off] Todo "done" = forget (delete)**: Completed todos are deleted, not marked done.
  → Acceptable for v1. Can change to metadata update later (forget + remember with todo_status=done). Keeps it simple.

- **[Risk] consolidation_report/events may return empty on fresh stores**: These track internal strengthening/decay.
  → Mitigation: Return empty results gracefully, document that these need time to accumulate.

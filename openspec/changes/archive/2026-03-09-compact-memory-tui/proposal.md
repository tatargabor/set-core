## Why

The `set-memory tui` dashboard is currently a single-column 66-char wide layout that aggregates all projects globally. When running from a project directory, users want to see only that project's metrics — not a mix of 81 projects. The layout also wastes most of a standard 160-column terminal.

## What Changes

- Add `--project` filtering to `query_report()` in `lib/metrics.py` — filter sessions by project name prefix match (so worktree sessions like `sales-raketa-wt-smoke..` are included when filtering for `sales-raketa`)
- Redesign `cmd_tui()` inline Python to use a 3-column ANSI layout that fits 160×80 terminals
- Auto-detect project from CWD (git root basename) when `--project` is not explicitly passed to `set-memory tui`
- Add a recent sessions list panel showing per-session breakdown (time, worktree name, injections, tokens, citations)

## Capabilities

### New Capabilities
- `compact-memory-tui`: 3-column ANSI layout for `set-memory tui` with per-project filtering and session list

### Modified Capabilities
- `metrics-reporting`: Add `project` parameter to `query_report()` for filtered queries
- `memory-tui-dashboard`: Update layout from single-column 66-wide to 3-column 160-wide with project scope

## Impact

- `lib/metrics.py` — `query_report()` signature change (backward-compatible, new optional param)
- `lib/memory/ui.sh` — `cmd_tui()` inline Python rewrite for new layout
- No new dependencies — stays pure ANSI, no Textual

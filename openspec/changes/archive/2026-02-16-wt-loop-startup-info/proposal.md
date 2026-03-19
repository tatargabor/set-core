## Why

When running multiple `wt-loop` instances in parallel (e.g., benchmark Run A vs Run B), the startup banner and terminal title are often identical — same worktree name, same task. There's no way to visually distinguish which terminal is which without checking the path manually.

## What Changes

- Add `--label <text>` flag to `wt-loop start` — a free-text identifier that appears in the banner and terminal title
- Expand the startup banner with: full path, git branch, label, `set-memory` status (active/inactive), and start timestamp
- Include the label in terminal title: `Ralph: <name> (<label>) [iter/max]`
- Store label in `loop-state.json` for MCP/status consumption
- macOS AppleScript: set explicit terminal tab title (currently missing)

## Capabilities

### New Capabilities
- `loop-startup-info`: Requirements for the expanded startup banner, `--label` flag, and enriched terminal title

### Modified Capabilities
- `ralph-loop`: Terminal title format changes to include label; state file gains `label` field

## Impact

- `bin/wt-loop`: `cmd_start` gains `--label` flag parsing; `cmd_run` gains expanded banner; `update_terminal_title` format changes; AppleScript block gets explicit title; `loop-state.json` schema adds `label` field
- GUI `start_ralph_loop_dialog`: may expose label field (future, out of scope for now)
- MCP consumers reading `loop-state.json`: new optional `label` field

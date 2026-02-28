## Why

`wt-orchestrate status` gives a one-shot CLI snapshot, but watching a multi-hour orchestration run requires repeatedly running it or wrapping in `watch`. There's no live view of log events, no keyboard-driven approve, and no way to see change progress update in real-time. A Textual TUI provides a live terminal dashboard that works over SSH, has zero new dependencies (textual 6.11.0 + rich 14.2.0 already installed), and can be shipped as a single `wt-orchestrate tui` subcommand.

## What Changes

- **New `wt-orchestrate tui` subcommand**: Launches a Textual app that reads `orchestration-state.json` on a timer (every 3-5s), displays live status with colored change cards
- **Header bar**: Overall orchestrator status, plan version, progress ratio, token totals, elapsed/remaining time
- **Change table**: Per-change rows with name, status (colored), iteration progress, tokens, gate results (test/review/verify/build)
- **Live log tail**: Bottom panel tailing `.claude/orchestration.log` with syntax-colored log levels
- **Keyboard actions**: `[a]` approve checkpoint, `[r]` force refresh, `[l]` toggle full log view, `[q]` quit
- **Approve via state file**: Same atomic write as `wt-orchestrate approve` — writes `checkpoints[-1].approved = true` to orchestration-state.json

## Capabilities

### New Capabilities
- `orchestrator-tui`: Textual-based terminal dashboard for monitoring orchestration runs — live status table, log tail, keyboard-driven checkpoint approval

### Modified Capabilities

## Impact

- **New files**: `bin/wt-orchestrate-tui` (or inline in wt-orchestrate as tui subcommand), Python Textual app
- **Modified files**: `bin/wt-orchestrate` (add `tui` subcommand dispatch)
- **Data source**: Reads `orchestration-state.json` (project root), `.claude/orchestration.log`, per-worktree `.claude/loop-state.json`
- **No new dependencies**: textual 6.11.0 and rich 14.2.0 already installed system-wide
- **No breaking changes**: Additive — new subcommand only

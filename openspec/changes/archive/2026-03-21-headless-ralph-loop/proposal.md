# Proposal: headless-ralph-loop

## Why

Ralph loops currently spawn a visible terminal window (gnome-terminal, xterm, kitty, Terminal.app) for each worktree. This is problematic: parallel orchestration with 5+ loops clutters the desktop, accidentally closing a terminal kills the loop, and it doesn't work on headless servers (no X11/Wayland). All monitoring capabilities already exist via `loop-state.json`, log files, `set-loop status/monitor`, and the GUI Control Center — the visible terminal is redundant.

## What Changes

- **Remove terminal spawning** from `cmd_start()` — replace `gnome-terminal`/`xterm`/`kitty`/`osascript` with background process (`nohup`/`setsid`)
- **Remove `--fullscreen` flag** — no longer applicable without a terminal window
- **Simplify `cmd_stop()`** — remove macOS `osascript` window-close logic, keep PID-based process kill
- **Redirect output to log file** — `set-loop run` stdout/stderr goes to a main log file instead of terminal
- **Remove terminal emulator detection** — no need to check for gnome-terminal/xterm/kitty availability

## Capabilities

### New Capabilities
_None — this is a refactor of existing behavior._

### Modified Capabilities
- **ralph-loop**: Loop spawning changes from terminal-based to headless background process.

## Impact

- **bin/set-loop**: `cmd_start()` terminal spawning block (~50 lines) replaced with ~5 lines of background process launch. `cmd_stop()` macOS osascript block removed.
- **lib/set_orch/dispatcher.py**: Comment update only (already fire-and-forget).
- **No breaking changes to external API**: `set-loop start/stop/status/monitor/history` commands unchanged. `loop-state.json` schema unchanged. GUI Control Center unaffected.
- **Improved stability**: Loop survives desktop session changes, no accidental terminal close kills.
- **Headless server support**: Works without X11/Wayland.

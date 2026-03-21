# Design: headless-ralph-loop

## Context

Ralph loops currently spawn a visible terminal window per worktree. The loop engine (`lib/loop/engine.sh` `cmd_run()`) runs inside that terminal, piping Claude CLI output to both terminal and log files via `tee`. The orchestrator (`dispatcher.py`) fires `set-loop start` and polls `loop-state.json` for status — it never interacts with the terminal window itself.

All monitoring is already headless: `loop-state.json`, per-iteration log files (`ralph-iter-NNN.log`), `set-loop status/monitor`, and the GUI Control Center. The terminal window is purely for visual debugging — redundant in production.

## Goals / Non-Goals

**Goals:**
- Replace terminal spawning with background process launch
- Maintain all existing monitoring capabilities
- Ensure loop survives desktop session changes
- Work on headless servers without X11

**Non-Goals:**
- Changing the loop engine internals (`cmd_run()`, iteration logic, Claude invocation)
- Changing `loop-state.json` schema
- Adding new monitoring capabilities

## Decisions

### D1: Use `nohup setsid` for process isolation

**Choice:** `nohup setsid bash -c "cd ... && set-loop run" > <logfile> 2>&1 &`

**Why over alternatives:**
- `nohup` alone: process still in caller's session, may get SIGHUP
- `setsid` alone: no `nohup` protection, output not redirected
- `tmux`/`screen`: unnecessary dependency, heavier than needed
- `disown`: bash-specific, less portable

`setsid` creates a new session (detached from controlling terminal), `nohup` ignores SIGHUP. Together they give full daemon-like isolation.

On macOS, `setsid` is not available by default. Use `nohup bash -c "..." &` with `disown` as fallback — macOS doesn't send SIGHUP to background jobs in the same way.

### D2: Redirect stdout/stderr to main log file

**Choice:** Redirect to `<log_dir>/ralph-main.log`

The `cmd_run()` banner and iteration markers go here instead of a terminal. Per-iteration logs (`ralph-iter-NNN.log`) are unchanged — they're already written by the engine independently.

### D3: PID capture via `$!` after backgrounding

After backgrounding the process, capture `$!` (last background PID) and write to `.set/ralph-terminal.pid`. The engine's `cmd_run()` also writes `$$` to the same file when it starts — the engine's write overwrites the shell wrapper PID with the actual loop PID, which is the correct one for `set-loop stop`.

### D4: Remove `--fullscreen` flag entirely

No deprecation period needed — this is an internal tool, not a public API. Remove the flag, the variable, and all terminal-specific `$fs_flag` logic.

## Risks / Trade-offs

- **[Risk] Loss of real-time visual debugging** → Mitigation: `tail -f <log_dir>/ralph-main.log` provides identical real-time output. `set-loop monitor` already exists for structured polling.
- **[Risk] PID tracking race** → The engine overwrites the PID file with `$$` when `cmd_run()` starts, which is the correct behavior. The brief window between background launch and engine start is covered by the orchestrator's 10-second polling for `loop-state.json`.

## Open Questions

_None._

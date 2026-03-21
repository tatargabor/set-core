# Tasks: headless-ralph-loop

## 1. Replace terminal spawning with background process

- [x] 1.1 Replace the entire terminal spawning block in `cmd_start()` (lines ~310-379 in `bin/set-loop`) with `nohup setsid` background launch on Linux and `nohup` with `disown` on macOS [REQ: ralph-loop-terminal-spawning]
- [x] 1.2 Redirect stdout/stderr of `set-loop run` to `<log_dir>/ralph-main.log` [REQ: ralph-loop-terminal-spawning]
- [x] 1.3 Capture background PID via `$!` and write to `.set/ralph-terminal.pid` [REQ: ralph-loop-terminal-spawning]
- [x] 1.4 Remove `--fullscreen` flag parsing from `cmd_start()` argument parser [REQ: fullscreen-terminal-option]
- [x] 1.5 Remove `fullscreen` variable and all `$fs_flag` references [REQ: fullscreen-terminal-option]

## 2. Simplify cmd_stop

- [x] 2.1 Remove the macOS `osascript` Terminal.app window-close block from `cmd_stop()` (lines ~441-450) [REQ: ralph-loop-stop-without-terminal]

## 3. Cleanup

- [x] 3.1 Update the `info "Spawning terminal..."` message to reflect headless launch [REQ: ralph-loop-terminal-spawning]
- [x] 3.2 Remove the "No supported terminal found" error fallback (line ~377) [REQ: terminal-emulator-detection]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `set-loop start` is invoked on Linux THEN `set-loop run` launches as background process without terminal emulator [REQ: ralph-loop-terminal-spawning, scenario: background-process-launch-on-linux]
- [x] AC-2: WHEN `set-loop start` is invoked on macOS THEN `set-loop run` launches as background process without Terminal.app/osascript [REQ: ralph-loop-terminal-spawning, scenario: background-process-launch-on-macos]
- [x] AC-3: WHEN `set-loop stop` is invoked THEN loop stops via PID kill without terminal cleanup [REQ: ralph-loop-stop-without-terminal, scenario: stop-on-linux]
- [x] AC-4: WHEN `set-loop start` is invoked on headless server THEN loop starts without error [REQ: ralph-loop-terminal-spawning, scenario: headless-server-compatibility]

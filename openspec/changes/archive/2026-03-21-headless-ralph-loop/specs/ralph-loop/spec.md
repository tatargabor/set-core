# Delta Spec: ralph-loop

## MODIFIED Requirements

### Requirement: Ralph loop terminal spawning
The Ralph loop SHALL start as a headless background process instead of spawning a visible terminal window.

#### Scenario: Background process launch on Linux
- **WHEN** `set-loop start` is invoked on Linux
- **THEN** `set-loop run` SHALL be launched via `nohup setsid bash -c "set-loop run" </dev/null &`
- **AND** stdout/stderr SHALL be redirected to a log file in the loop log directory
- **AND** the shell PID SHALL be saved to `.set/ralph-terminal.pid`
- **AND** no terminal emulator (gnome-terminal, xterm, kitty) SHALL be invoked

#### Scenario: Background process launch on macOS
- **WHEN** `set-loop start` is invoked on macOS
- **THEN** `set-loop run` SHALL be launched via `nohup bash -c "set-loop run" </dev/null &`
- **AND** stdout/stderr SHALL be redirected to a log file in the loop log directory
- **AND** no Terminal.app window or osascript SHALL be invoked

#### Scenario: Loop survives desktop session
- **WHEN** a Ralph loop is running as a background process
- **AND** the user's desktop session ends or changes
- **THEN** the loop process SHALL continue running

#### Scenario: Headless server compatibility
- **WHEN** `set-loop start` is invoked on a system without X11/Wayland
- **THEN** the loop SHALL start successfully without error
- **AND** no terminal emulator detection SHALL be performed

### Requirement: Ralph loop stop without terminal
The `set-loop stop` command SHALL stop loops using PID-based process kill only, without terminal window management.

#### Scenario: Stop on Linux
- **WHEN** `set-loop stop` is invoked
- **THEN** the process tree rooted at the saved PID SHALL be killed
- **AND** no terminal-specific cleanup SHALL be performed

#### Scenario: Stop on macOS
- **WHEN** `set-loop stop` is invoked on macOS
- **THEN** the process tree rooted at the saved PID SHALL be killed
- **AND** no osascript Terminal.app window-close SHALL be performed

## REMOVED Requirements

### Requirement: Fullscreen terminal option
The `--fullscreen` flag for `set-loop start` is removed.

- **Reason**: No terminal window to fullscreen.
- **Migration**: Remove `--fullscreen` from any scripts or orchestration configs. No alternative needed — monitoring is via `set-loop status/monitor` and GUI.

### Requirement: Terminal emulator detection
Detection of gnome-terminal, xterm, kitty, and Terminal.app is removed from `cmd_start()`.

- **Reason**: No terminal window is spawned.
- **Migration**: None needed. The "No supported terminal found" error is eliminated — loops work on any system.

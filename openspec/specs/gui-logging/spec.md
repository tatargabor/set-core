# gui-logging Specification

## Purpose
TBD - created by archiving change gui-debug-logging. Update Purpose after archive.
## Requirements
### Requirement: Log file initialization at startup
The system SHALL create a rotating log file when the GUI starts. The log file SHALL be located at the platform's temp directory (`/tmp/set-control.log` on macOS/Linux, `%TEMP%\set-control.log` on Windows). The RotatingFileHandler SHALL use 5 MB max file size with 3 backup files.

#### Scenario: GUI startup creates log file
- **WHEN** the GUI application starts via `gui/main.py`
- **THEN** a log file is created at the platform temp directory and a startup message is written with the application version and Python version

#### Scenario: Log rotation on size limit
- **WHEN** the log file exceeds 5 MB
- **THEN** the file is rotated and up to 3 backup files are kept (`.log.1`, `.log.2`, `.log.3`)

### Requirement: Per-module logger hierarchy
Each GUI module SHALL use a child logger under the `set-control` root logger, named by module (e.g., `set-control.handlers`, `set-control.macos`, `set-control.workers.status`).

#### Scenario: Module logger naming
- **WHEN** a GUI module initializes its logger
- **THEN** it uses `logging.getLogger("set-control.<module-name>")` to create a hierarchically named logger

### Requirement: User action logging
All user-triggered handler methods (`on_double_click`, `on_focus`, `on_close_editor`, `on_new`, `on_work`, `on_add`, `on_close`, `git_merge`, `git_push`, `git_pull`, `git_fetch`, `create_worktree`) SHALL log at INFO level on entry with the key parameters (project, change_id, path).

#### Scenario: Double-click action logging
- **WHEN** the user double-clicks a worktree row
- **THEN** the log SHALL contain the method name, project, change_id, path, and the action taken (window found, window focused, editor opened, or no worktree selected)

#### Scenario: Git operation logging
- **WHEN** the user triggers a git operation (merge, push, pull, fetch)
- **THEN** the log SHALL contain the operation name, worktree path, and the command executed

### Requirement: Platform call logging
All platform abstraction methods (`find_window_by_title`, `focus_window`, `close_window`, `find_window_by_pid`) SHALL log at DEBUG level with input parameters and return values.

#### Scenario: Window search logging
- **WHEN** `find_window_by_title` is called
- **THEN** the log SHALL contain the search title, app_name, and the result (window title found or None)

#### Scenario: Window focus logging
- **WHEN** `focus_window` is called
- **THEN** the log SHALL contain the window_id, app_name, and whether the focus succeeded (True/False)

### Requirement: Subprocess call logging
All `subprocess.Popen` and `subprocess.run` calls in handler and platform code SHALL log at DEBUG level with the command list. For `subprocess.run`, the return code SHALL also be logged. For failures, stderr SHALL be logged at ERROR level.

#### Scenario: Subprocess success logging
- **WHEN** a subprocess call completes successfully
- **THEN** the log SHALL contain the command and return code

#### Scenario: Subprocess failure logging
- **WHEN** a subprocess call fails (non-zero return code or exception)
- **THEN** the log SHALL contain the command, return code, and stderr output at ERROR level

### Requirement: Exception safety for Qt signal handlers
All `on_*` methods connected to Qt signals in `handlers.py` SHALL be wrapped with exception logging so that exceptions are logged at ERROR level with full traceback before being re-raised.

#### Scenario: Exception in signal handler
- **WHEN** an exception occurs inside a Qt signal-connected handler (e.g., `on_double_click`)
- **THEN** the exception and full traceback SHALL be logged at ERROR level, and the exception SHALL be re-raised

### Requirement: Menu action logging
Context menu and main menu actions SHALL log at INFO level with the action name and relevant parameters (worktree project/change_id, action type).

#### Scenario: Context menu action
- **WHEN** the user selects a context menu action on a worktree row
- **THEN** the log SHALL contain the action name and the target worktree's project and change_id

### Requirement: Worker thread logging
All background worker threads (FeatureWorker, ChatWorker, UsageWorker) SHALL use child loggers under `set-control.workers.<name>`. Each poll cycle SHALL log at DEBUG level. Errors and timeouts SHALL log at ERROR level with the exception details.

#### Scenario: FeatureWorker poll logging
- **WHEN** the FeatureWorker completes a poll cycle
- **THEN** it logs at DEBUG level the number of projects polled and per-project results

#### Scenario: FeatureWorker subprocess failure
- **WHEN** a `set-memory` or `set-openspec` subprocess fails or times out
- **THEN** it logs at ERROR level with the command, project name, and exception message

#### Scenario: UsageWorker poll cycle logging
- **WHEN** the UsageWorker starts a poll cycle
- **THEN** it logs at DEBUG level the number of accounts being fetched
- **AND** after each account fetch, it logs the result (success with source, or failure)
- **AND** after the cycle completes, it logs before entering sleep

#### Scenario: UsageWorker API failure logging
- **WHEN** a UsageWorker API call fails across all fallback methods (curl-cffi, curl subprocess, urllib)
- **THEN** it logs at WARNING level with the account name

### Requirement: Signal handler exception logging
When a signal handler catches an exception via the error boundary, it SHALL log at ERROR level with the full traceback, the signal name, and the data that caused the error.

#### Scenario: Exception in update_status handler
- **WHEN** `update_status()` catches an exception
- **THEN** the log contains `ERROR set-control.main_window: update_status failed:` followed by the traceback

### Requirement: Worker error logging
Background worker threads (StatusWorker, TeamWorker, ChatWorker, UsageWorker) SHALL log errors at ERROR level when polling fails. Normal polling cycles SHALL NOT be logged to avoid log noise.

#### Scenario: Worker polling failure
- **WHEN** a background worker's poll cycle fails with an exception
- **THEN** the error and traceback SHALL be logged at ERROR level

#### Scenario: Normal polling cycle
- **WHEN** a background worker completes a poll cycle successfully
- **THEN** no log entry SHALL be written (to avoid noise)

### Requirement: Log message format
Log messages SHALL use the format: `YYYY-MM-DD HH:MM:SS LEVEL module:function message`. The format SHALL include enough context to identify what happened without reading source code.

#### Scenario: Log format example
- **WHEN** any log message is written
- **THEN** it SHALL follow the format `2026-02-13 08:15:32 INFO handlers:on_double_click project=mediapipe change=master action=open_editor`


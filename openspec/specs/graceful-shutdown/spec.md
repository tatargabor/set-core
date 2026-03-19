# graceful-shutdown Specification

## Purpose
TBD - created by archiving change graceful-shutdown. Update Purpose after archive.
## Requirements
### Requirement: Sentinel graceful shutdown command
The sentinel SHALL support a `--shutdown` flag that initiates an orderly shutdown sequence. The shutdown SHALL signal all running agents to stop, wait for them to exit cleanly, update the state file with shutdown metadata, and then exit.

#### Scenario: User triggers graceful shutdown
- **WHEN** the user runs `set-sentinel --shutdown` while a sentinel is running
- **THEN** the sentinel sends SIGTERM to the orchestrator process
- **THEN** the orchestrator sends SIGTERM to all running agent processes (wt-loop)
- **THEN** the sentinel waits up to 60 seconds for all agents to exit
- **THEN** the state file is updated with `shutdown_at` timestamp and status `"shutdown"`
- **THEN** the sentinel exits with code 0

#### Scenario: Shutdown with no running sentinel
- **WHEN** the user runs `set-sentinel --shutdown` but no sentinel is running
- **THEN** the command prints "No sentinel running" and exits with code 0

#### Scenario: Shutdown timeout exceeded
- **WHEN** agents do not exit within the 60-second grace period
- **THEN** the sentinel sends SIGKILL to remaining agent processes
- **THEN** changes with killed agents are marked as `"stalled"` in state
- **THEN** the sentinel exits with code 0

### Requirement: Agent graceful stop on SIGTERM
The agent loop (wt-loop) SHALL handle SIGTERM by completing its current iteration, committing any uncommitted work, and exiting cleanly.

#### Scenario: Agent receives SIGTERM during task execution
- **WHEN** wt-loop receives SIGTERM while a Claude session is running
- **THEN** wt-loop sets a `stop_requested` flag
- **THEN** after the current Claude session completes, wt-loop commits all uncommitted changes with message "wip: graceful shutdown — incomplete task"
- **THEN** wt-loop writes `last_commit` hash to its loop-state.json
- **THEN** wt-loop exits with code 0

#### Scenario: Agent receives SIGTERM between iterations
- **WHEN** wt-loop receives SIGTERM between loop iterations (idle)
- **THEN** wt-loop exits immediately with code 0 (no WIP to commit)

### Requirement: State persistence for resume
The orchestration state file SHALL contain sufficient metadata to resume after a shutdown, including shutdown timestamp and per-change commit references.

#### Scenario: State updated during graceful shutdown
- **WHEN** the orchestrator performs graceful shutdown
- **THEN** the state file `status` field is set to `"shutdown"`
- **THEN** a `shutdown_at` ISO timestamp is written to the state file
- **THEN** each running change's state includes `last_commit` (the HEAD of its worktree branch at shutdown time)

#### Scenario: State preserved for pending changes
- **WHEN** shutdown occurs with changes in `pending` status
- **THEN** pending changes remain `pending` in the state file (no modification)

### Requirement: Resume after shutdown
The sentinel SHALL detect a previous shutdown state on startup and resume orchestration from where it stopped.

#### Scenario: Sentinel starts with shutdown state
- **WHEN** the sentinel starts and finds state file with status `"shutdown"`
- **THEN** the sentinel validates each worktree still exists on disk
- **THEN** for each running change at shutdown: verifies the worktree branch HEAD matches `last_commit`
- **THEN** changes with valid worktrees are set back to `"running"` and re-dispatched
- **THEN** changes with missing/mismatched worktrees are set to `"pending"` for fresh dispatch
- **THEN** the state status is set to `"running"` and orchestration continues

#### Scenario: Resume with missing worktrees
- **WHEN** the sentinel resumes but a worktree directory no longer exists (e.g., was in `/tmp/` and machine rebooted)
- **THEN** the change is reset to `"pending"` with cleared `worktree_path`
- **THEN** the branch is cleaned up if it still exists
- **THEN** a warning is logged: "Worktree missing for change X, resetting to pending"

### Requirement: Persistent project directory for E2E
The E2E scaffold scripts SHALL support a `--project-dir` flag to create the test project in a persistent (non-volatile) directory instead of `/tmp/`.

#### Scenario: E2E scaffold with custom directory
- **WHEN** the user runs `./tests/e2e/run.sh --project-dir ~/e2e-tests`
- **THEN** the project is created at `~/e2e-tests/minishop-runN` instead of `/tmp/minishop-runN`
- **THEN** the project survives system reboots

#### Scenario: E2E scaffold without flag
- **WHEN** the user runs `./tests/e2e/run.sh` without `--project-dir`
- **THEN** the default `/tmp/` location is used (backward compatible)

### Requirement: Shutdown API endpoint
The wt-web API SHALL expose a `POST /api/{project}/shutdown` endpoint that triggers graceful shutdown of the orchestration.

#### Scenario: Shutdown via API
- **WHEN** a client sends `POST /api/{project}/shutdown`
- **THEN** the API sends SIGUSR1 to the running sentinel process (from PID file)
- **THEN** the API returns `{"ok": true, "message": "Shutdown initiated"}` with status 200
- **THEN** the sentinel performs the graceful shutdown sequence

#### Scenario: Shutdown API with no running sentinel
- **WHEN** a client sends `POST /api/{project}/shutdown` but no sentinel is running
- **THEN** the API returns `{"ok": false, "error": "No sentinel running"}` with status 409

### Requirement: Settings page shutdown controls
The wt-web Settings page SHALL include a Shutdown button with confirmation dialog, a status indicator showing shutdown state, and a Resume button when in shutdown state.

#### Scenario: User clicks Shutdown in Settings
- **WHEN** the user clicks the "Shutdown" button on the Settings page
- **THEN** a confirmation dialog appears: "This will gracefully stop all agents and the orchestrator. Continue?"
- **THEN** on confirm, the UI calls `POST /api/{project}/shutdown`
- **THEN** the button shows "Shutting down..." with a spinner while the shutdown is in progress

#### Scenario: Settings page shows shutdown state
- **WHEN** the orchestration status is `"shutdown"`
- **THEN** the Settings page shows a status badge "Shutdown" with a yellow/amber indicator
- **THEN** a "Resume" button is displayed instead of "Shutdown"

#### Scenario: User clicks Resume in Settings
- **WHEN** the user clicks "Resume" on the Settings page while status is `"shutdown"`
- **THEN** the UI calls the existing start/resume API endpoint
- **THEN** the sentinel resumes orchestration from shutdown state


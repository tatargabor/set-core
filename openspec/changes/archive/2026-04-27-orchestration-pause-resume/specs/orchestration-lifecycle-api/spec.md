# Spec: orchestration-lifecycle-api

## ADDED Requirements

## IN SCOPE
- API endpoint to start/resume sentinel for a project from the web dashboard
- API endpoint to pause/resume individual changes
- Frontend: Resume button for both "stopped" and "shutdown" states
- Frontend: per-change pause/resume controls on Dashboard
- Ralph graceful iteration stop on SIGTERM (finish current, don't start next)
- Shutdown progress UI: live list of processes and their stop status
- Shutdown progress events in the event log

## OUT OF SCOPE
- Scheduled pause/resume (e.g., pause at midnight, resume at 8am)
- Remote machine power management
- Force-kill mode (already exists via stop endpoint)
- Changes to the sentinel's "shutdown" status write (already works correctly)
- Modifying engine.py cleanup to write "shutdown" (sentinel already owns this)

### Requirement: Start endpoint spawns sentinel
The API SHALL provide a `POST /api/{project}/start` endpoint that starts orchestration for a project by spawning a detached `set-sentinel` process.

#### Scenario: Start from shutdown state
- **WHEN** project orchestration status is "shutdown" and user calls `POST /api/{project}/start`
- **THEN** the API spawns a detached `set-sentinel --spec <spec-path>` process, returns `{ok: true, pid: <sentinel_pid>}`, and the sentinel resumes from existing state

#### Scenario: Start from stopped state
- **WHEN** project orchestration status is "stopped" (crash) and user calls `POST /api/{project}/start`
- **THEN** the API spawns sentinel which recovers orphaned changes and resumes dispatch

#### Scenario: Start when already running
- **WHEN** sentinel is already running for the project and user calls `POST /api/{project}/start`
- **THEN** the API returns HTTP 409 with message "Sentinel already running"

#### Scenario: Start with no state file
- **WHEN** no `orchestration-state.json` exists and user calls `POST /api/{project}/start`
- **THEN** the API spawns sentinel which begins fresh planning from the spec

#### Scenario: Start with corrupt state file
- **WHEN** `orchestration-state.json` exists but contains invalid JSON and user calls `POST /api/{project}/start`
- **THEN** the API returns HTTP 500 with message describing the corruption

### Requirement: Ralph graceful iteration stop
On receiving SIGTERM, the Ralph loop SHALL finish its current iteration (allow the active Claude session to complete its current tool call) and then exit without starting a new iteration. Child processes spawned during the iteration SHALL be terminated gracefully.

#### Scenario: SIGTERM during active iteration
- **WHEN** Ralph loop receives SIGTERM while a Claude session iteration is in progress
- **THEN** Ralph sets a shutdown flag, allows the current iteration to complete, commits any uncommitted work, and exits with code 0

#### Scenario: SIGTERM between iterations
- **WHEN** Ralph loop receives SIGTERM between iterations (in the sleep/poll phase)
- **THEN** Ralph exits immediately with code 0

#### Scenario: Child process cleanup on Ralph exit
- **WHEN** Ralph exits due to SIGTERM and has child processes running (dev server, test runner, build)
- **THEN** Ralph sends SIGTERM to child processes, waits up to 10 seconds, then sends SIGKILL to any remaining

### Requirement: Graceful shutdown cascade
The shutdown signal SHALL propagate top-down through the process tree. The sentinel owns the "shutdown" status write.

#### Scenario: Graceful shutdown via SIGUSR1
- **WHEN** sentinel receives SIGUSR1 (from `set-sentinel --shutdown` or `POST /api/{project}/shutdown`)
- **THEN** the sentinel sends SIGTERM to the orchestrator, which sends SIGTERM to each Ralph loop PID from state, waits for them to exit (up to 90 seconds), and exits. The sentinel then sets orchestration status to "shutdown"

#### Scenario: Orchestrator emits shutdown progress events
- **WHEN** graceful shutdown is in progress
- **THEN** the orchestrator emits JSONL events for each step: `SHUTDOWN_STARTED`, `CHANGE_STOPPING {name}`, `CHANGE_STOPPED {name}`, `SHUTDOWN_COMPLETE`

#### Scenario: Crash sets stopped status
- **WHEN** the orchestrator process crashes unexpectedly (SIGKILL, unhandled exception)
- **THEN** engine.py cleanup sets status to "stopped" and the sentinel does NOT overwrite it with "shutdown"

### Requirement: Per-change pause and resume
The API SHALL provide endpoints to pause and resume individual changes. Resume SHALL re-dispatch the Ralph loop if it is not running.

#### Scenario: Pause a running change
- **WHEN** a change has status "running" and user calls `POST /api/{project}/changes/{name}/pause`
- **THEN** the change status is set to "paused" and the Ralph process receives SIGTERM (graceful iteration stop)

#### Scenario: Resume a paused change
- **WHEN** a change has status "paused" and user calls `POST /api/{project}/changes/{name}/resume`
- **THEN** a new Ralph loop is dispatched for the change (re-dispatch), change status becomes "running", respecting max_parallel limit

#### Scenario: Resume when at max parallel capacity
- **WHEN** a change is "paused" and max_parallel running changes are already active and user calls resume
- **THEN** the API returns HTTP 429 with message "Max parallel changes reached, try again later"

#### Scenario: Pause an already paused change
- **WHEN** a change has status "paused" and user calls `POST /api/{project}/changes/{name}/pause`
- **THEN** the API returns HTTP 200 (idempotent, no state change)

#### Scenario: Resume an already running change
- **WHEN** a change has status "running" and user calls `POST /api/{project}/changes/{name}/resume`
- **THEN** the API returns HTTP 200 (idempotent, no state change)

#### Scenario: Pause a non-running change
- **WHEN** a change has status other than "running" or "paused" (e.g., "pending", "merged", "failed") and user calls pause
- **THEN** the API returns HTTP 409 with message "Change is not in a pausable state"

### Requirement: Frontend shows resume for resumable states
The web dashboard SHALL show a Resume button for all resumable orchestration states and display shutdown progress during active shutdown.

#### Scenario: Resume button for shutdown state
- **WHEN** orchestration status is "shutdown"
- **THEN** the Settings page shows a green "Resume" button with label "Paused (clean shutdown)"

#### Scenario: Resume button for stopped state
- **WHEN** orchestration status is "stopped"
- **THEN** the Settings page shows an amber "Resume" button with label "Stopped (unexpected)"

#### Scenario: Shutdown progress list
- **WHEN** a graceful shutdown is in progress (between SHUTDOWN_STARTED and SHUTDOWN_COMPLETE events)
- **THEN** the Dashboard shows a shutdown progress panel listing each change/process with status: "Stopping..." (spinner), "Stopped" (checkmark), or "Timed out" (warning)

#### Scenario: Per-change controls on dashboard
- **WHEN** changes are displayed on the Dashboard
- **THEN** running changes show a "Pause" button and paused changes show a "Resume" button

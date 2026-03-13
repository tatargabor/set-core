## ADDED Requirements

### Requirement: Project listing endpoint
The server SHALL expose `GET /api/projects` returning all registered projects from `~/.config/wt-tools/projects.json`. Each entry SHALL include the project name, path, whether orchestration state exists, and a quick status (`running`, `done`, `checkpoint`, `idle`).

#### Scenario: Multiple registered projects
- **WHEN** projects.json contains 3 projects, 1 with active orchestration and 2 without
- **THEN** the response is a JSON array of 3 objects with `name`, `path`, `has_orchestration` (bool), and `status` fields

#### Scenario: No projects registered
- **WHEN** projects.json is empty or missing
- **THEN** the response is an empty JSON array

### Requirement: Orchestration state endpoint
The server SHALL expose `GET /api/{project}/state` returning the full orchestration state parsed via `load_state()`. The response SHALL include all fields from the `OrchestratorState` dataclass serialized as JSON.

#### Scenario: Active orchestration
- **WHEN** requesting state for a project with a valid `orchestration-state.json`
- **THEN** the response contains `status`, `changes` array, `checkpoints`, `plan_version`, token aggregates, and timing data

#### Scenario: No orchestration state
- **WHEN** requesting state for a project without `orchestration-state.json`
- **THEN** the server returns HTTP 404 with `{"error": "no orchestration state"}`

### Requirement: Changes query endpoint
The server SHALL expose `GET /api/{project}/changes` returning the changes array with optional `?status=` query parameter for filtering. `GET /api/{project}/changes/{name}` SHALL return a single change by name.

#### Scenario: Filter by status
- **WHEN** requesting `/api/project1/changes?status=running`
- **THEN** only changes with `status == "running"` are returned

#### Scenario: Single change detail
- **WHEN** requesting `/api/project1/changes/add-auth`
- **THEN** the full change object is returned including token breakdown, gate results, watchdog state

#### Scenario: Change not found
- **WHEN** requesting a change name that does not exist
- **THEN** the server returns HTTP 404

### Requirement: Worktree listing endpoint
The server SHALL expose `GET /api/{project}/worktrees` returning active git worktrees for the project, enriched with loop-state data (iteration count, max iterations) where available.

#### Scenario: Project with active worktrees
- **WHEN** a project has 3 worktrees, 2 with running wt-loop agents
- **THEN** the response lists all 3 worktrees with path, branch, and loop-state (`iteration`, `max_iterations`) for the 2 active ones

### Requirement: Agent activity endpoint
The server SHALL expose `GET /api/{project}/activity` returning `.claude/activity.json` contents from each active worktree, showing what agents are currently doing.

#### Scenario: Active agents
- **WHEN** 2 worktrees have agents running with activity.json
- **THEN** the response includes per-worktree activity with `skill`, `skill_args`, `broadcast`, and staleness indicator

### Requirement: Log tail endpoint
The server SHALL expose `GET /api/{project}/log?lines=N` returning the last N lines (default 500) of `orchestration.log`.

#### Scenario: Large log file
- **WHEN** orchestration.log is 15MB with 100K lines and `?lines=500` is requested
- **THEN** only the last 500 lines are returned, read efficiently without loading the full file

### Requirement: Checkpoint approve endpoint
The server SHALL expose `POST /api/{project}/approve` which marks the latest checkpoint as approved in `orchestration-state.json`. The write MUST use flock to coordinate with bash orchestration. The write MUST use atomic file operations (`save_state()`).

#### Scenario: Approve at checkpoint
- **WHEN** orchestration is at `status: "checkpoint"` and approve is called
- **THEN** `checkpoints[-1].approved` is set to `true` with `approved_at` timestamp, and the bash polling loop picks up the change within 10 seconds

#### Scenario: Approve when not at checkpoint
- **WHEN** approve is called but status is not `checkpoint`
- **THEN** the server returns HTTP 409 with `{"error": "not at checkpoint"}`

### Requirement: Stop orchestration endpoint
The server SHALL expose `POST /api/{project}/stop` which terminates the orchestration process using `safe_kill()` with identity verification.

#### Scenario: Stop running orchestration
- **WHEN** orchestration is running and stop is called
- **THEN** the main orchestrator PID is terminated via `safe_kill()` with `wt-orchestrate` cmdline verification, and state status is updated to `stopped`

#### Scenario: Stop already stopped
- **WHEN** stop is called but no orchestration process is running
- **THEN** the server returns HTTP 409 with `{"error": "not running"}`

### Requirement: Stop single change endpoint
The server SHALL expose `POST /api/{project}/changes/{name}/stop` which terminates the Ralph process for a specific change using `safe_kill()`.

#### Scenario: Stop running change
- **WHEN** a change has `ralph_pid` and is `status: "running"`
- **THEN** the Ralph process is killed via `safe_kill()` with `wt-loop` cmdline verification

### Requirement: Skip change endpoint
The server SHALL expose `POST /api/{project}/changes/{name}/skip` which marks a change as skipped in state.json.

#### Scenario: Skip pending change
- **WHEN** a change with `status: "pending"` is skipped
- **THEN** the change status is updated to `skipped` with flock + atomic write

### Requirement: WebSocket streaming
The server SHALL expose `WS /ws/{project}/stream` which pushes real-time updates to connected clients. On connect, the full current state SHALL be sent. After that, only deltas are pushed when the underlying files change.

#### Scenario: Client connects
- **WHEN** a WebSocket client connects to `/ws/project1/stream`
- **THEN** an initial `state_update` event is sent with the full orchestration state

#### Scenario: State file changes
- **WHEN** `orchestration-state.json` is modified by the bash orchestration
- **THEN** all connected WebSocket clients receive a `state_update` event within 1 second

#### Scenario: New log lines
- **WHEN** new lines are appended to `orchestration.log`
- **THEN** all connected clients receive a `log_lines` event with the new lines

#### Scenario: Checkpoint becomes pending
- **WHEN** orchestration status transitions to `checkpoint`
- **THEN** all clients receive a `checkpoint_pending` event with checkpoint details

### Requirement: File watching
The server SHALL use `watchfiles` to monitor orchestration state and log files for changes. Changes MUST be detected and pushed to WebSocket clients within 1 second of file modification.

#### Scenario: Watched files
- **WHEN** the server starts for a project
- **THEN** it watches `orchestration-state.json`, `orchestration.log`, and worktree `loop-state.json` files

#### Scenario: Watcher resilience
- **WHEN** a watched file is deleted and recreated (log rotation, state reinit)
- **THEN** the watcher recovers and continues monitoring the new file

### Requirement: State write locking
All API write operations MUST acquire a flock on the state lock file before reading/modifying/writing `orchestration-state.json`. The lock mechanism MUST be compatible with the bash `with_state_lock` function.

#### Scenario: Concurrent write from API and bash
- **WHEN** the web API and bash orchestration both attempt to write state.json simultaneously
- **THEN** one acquires the flock first, completes its write, then the other proceeds — no corruption occurs

## ADDED Requirements

### Requirement: Project selector
The SPA SHALL display a project selector dropdown populated from `GET /api/projects`. The last-selected project SHALL be persisted in localStorage and auto-selected on reload.

#### Scenario: Multiple projects
- **WHEN** 3 projects are registered and user opens the dashboard
- **THEN** the project selector shows all 3 with status indicators (running=green, checkpoint=yellow, idle=gray)

#### Scenario: Auto-select last project
- **WHEN** user previously selected "craftbrew" and reopens the dashboard
- **THEN** "craftbrew" is auto-selected and its data loads immediately

### Requirement: Orchestration status header
The dashboard SHALL display an orchestration status header showing: status with color-coded indicator, plan version, replan cycle, completed/total changes count, cumulative token usage with cache breakdown, active time, elapsed time, and time limit with remaining.

#### Scenario: Running orchestration
- **WHEN** orchestration is running with 3/7 changes done and 1.2M tokens used
- **THEN** the header shows green "RUNNING" badge, "3/7 done", "1.2M tokens", active/elapsed times

#### Scenario: Checkpoint status
- **WHEN** orchestration is at checkpoint
- **THEN** the header shows yellow "CHECKPOINT" badge with a prominent approve banner

### Requirement: Change table
The dashboard SHALL display a table of all changes with columns: Name (with dependency indicators), Status (color-coded with icon), Iteration (from loop-state), Duration, Token breakdown (in/out/cache), and Gates (T/B/E/R/V/S with pass/fail/skip indicators and timing).

#### Scenario: Change with all gates
- **WHEN** a change has completed test (pass, 12s), build (pass, 8s), review (pass), verify (pass)
- **THEN** the gates column shows "T:check:12s B:check:8s R:check V:check" with green indicators

#### Scenario: Running change with iteration
- **WHEN** a change is running with loop-state showing iteration 5/20
- **THEN** the iteration column shows "5/20"

#### Scenario: Pending change with dependencies
- **WHEN** a change depends on "add-auth" which is still running
- **THEN** the name column shows the dependency indicator "(depends on: add-auth)"

### Requirement: Log stream viewer
The dashboard SHALL include a log viewer that displays orchestration log lines with color coding by level (ERROR=red, WARN=yellow, REPLAN=cyan). New lines SHALL append in real-time via WebSocket. The viewer SHALL use virtual scrolling for performance with large logs.

#### Scenario: Real-time log append
- **WHEN** new log lines arrive via WebSocket
- **THEN** they appear at the bottom of the log viewer with auto-scroll (if user is at bottom)

#### Scenario: Manual scroll
- **WHEN** user scrolls up to read older logs
- **THEN** auto-scroll is paused and a "Jump to bottom" button appears

### Requirement: Checkpoint control panel
When orchestration is at checkpoint status, the dashboard SHALL display a prominent control panel with Approve, Stop, and Replan buttons. The Approve button SHALL call `POST /api/{project}/approve`. The Stop button SHALL call `POST /api/{project}/stop`. Actions SHALL show loading state and confirmation on success.

#### Scenario: Approve checkpoint
- **WHEN** user clicks Approve
- **THEN** the API is called, the button shows loading state, and on success the status transitions to "running"

#### Scenario: Stop orchestration
- **WHEN** user clicks Stop
- **THEN** a confirmation dialog appears, and on confirm the API is called to stop orchestration

### Requirement: Per-change actions
Each change row in the table SHALL have a context menu or action buttons for Stop (running changes) and Skip (pending changes). Actions SHALL call the corresponding API endpoints.

#### Scenario: Stop a running change
- **WHEN** user clicks Stop on a running change "add-cart"
- **THEN** `POST /api/{project}/changes/add-cart/stop` is called and the change status updates

#### Scenario: Skip a pending change
- **WHEN** user clicks Skip on a pending change "add-search"
- **THEN** `POST /api/{project}/changes/add-search/skip` is called and the row updates to "skipped"

### Requirement: Browser notifications
The SPA SHALL request browser notification permission on first visit. When a `checkpoint_pending` or `error` WebSocket event is received and the tab is not focused, a browser notification SHALL be displayed.

#### Scenario: Checkpoint notification
- **WHEN** orchestration reaches checkpoint and the browser tab is not focused
- **THEN** a browser notification shows "Checkpoint - 3/7 done" with the project name

#### Scenario: Error notification
- **WHEN** a change fails and the tab is not focused
- **THEN** a browser notification shows "Error: add-cart failed" with the project name

#### Scenario: Tab focused
- **WHEN** checkpoint event arrives and the tab IS focused
- **THEN** no browser notification is shown (the UI itself shows the status)

### Requirement: WebSocket reconnection
The SPA SHALL automatically reconnect to the WebSocket if the connection drops. On reconnect, it SHALL fetch the full state via REST to resync.

#### Scenario: Server restart
- **WHEN** the FastAPI server restarts (systemd restart)
- **THEN** the SPA detects disconnect, retries connection with exponential backoff, and resyncs state on reconnect

### Requirement: Responsive layout
The dashboard SHALL use a two-panel layout: change table (upper) and log viewer (lower), with a resizable split. The log panel SHALL be collapsible.

#### Scenario: Toggle log panel
- **WHEN** user clicks the log panel toggle
- **THEN** the log panel collapses and the change table takes full height (or vice versa)

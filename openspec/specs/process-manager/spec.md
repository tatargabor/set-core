# Spec: process-manager

## ADDED Requirements

## IN SCOPE
- API endpoint to discover all processes related to a project (sentinel, orchestrator, ralph loops, claude agents)
- Process tree visualization on Settings page
- Stop individual process or stop all in correct order
- Process info: PID, uptime, CPU%, memory, command

## OUT OF SCOPE
- Starting processes from this UI (sentinel start is on Sentinel page)
- Process log viewing (logs are on other pages)
- Auto-restart or watchdog functionality
- Cross-project process management

### Requirement: Process discovery API

The system SHALL provide a GET `/api/:project/processes` endpoint that returns a tree of all processes related to the project. The tree SHALL be organized as: sentinel (root) → orchestrator → ralph loops → claude agents. Each process node SHALL include pid, command, uptime_seconds, cpu_percent, memory_mb, and children array. Discovery SHALL use PID files from `.set/` directory and `ps` command to find child processes.

#### Scenario: Running orchestration with agents
- **WHEN** GET `/api/:project/processes` is called while orchestration is running
- **THEN** response contains a tree with sentinel at root, orchestrator as child, and claude agents as leaves
- **AND** each node has pid, uptime_seconds, cpu_percent, memory_mb

#### Scenario: No processes running
- **WHEN** GET `/api/:project/processes` is called with no running processes
- **THEN** response contains an empty processes array

### Requirement: Process stop API

The system SHALL provide a POST `/api/:project/processes/:pid/stop` endpoint that sends SIGTERM to the specified process. The system SHALL also provide a POST `/api/:project/processes/stop-all` endpoint that stops all processes in reverse tree order (leaves first, root last) with SIGTERM, waiting up to 5 seconds per process before SIGKILL fallback.

#### Scenario: Stop single process
- **WHEN** POST `/api/:project/processes/1234/stop` is called
- **THEN** SIGTERM is sent to PID 1234
- **AND** response confirms the signal was sent

#### Scenario: Stop all processes
- **WHEN** POST `/api/:project/processes/stop-all` is called
- **THEN** processes are stopped bottom-up (claude agents → orchestrator → sentinel)
- **AND** orchestration state is set to "stopped"

### Requirement: Process tree UI

The Settings page SHALL display a "Processes" section showing the process tree with indentation. Each process row SHALL show: PID, command (truncated), uptime, CPU%, memory, and a Stop button. A "Stop All" button SHALL appear at the top. The tree SHALL auto-refresh every 5 seconds. Stop buttons SHALL have loading state and confirmation per web-frontend rules.

#### Scenario: Process tree display
- **WHEN** the user views the Settings page with running processes
- **THEN** a process tree is displayed with sentinel → orchestrator → agents hierarchy
- **AND** each row shows PID, uptime, CPU, memory, and a Stop button

#### Scenario: Stop All button
- **WHEN** the user clicks "Stop All"
- **THEN** all processes are stopped in correct order
- **AND** the tree updates to show no running processes

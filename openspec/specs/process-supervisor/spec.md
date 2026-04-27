# Process Supervisor

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Per-project sentinel agent spawning and lifecycle management
- Per-project orchestration spawning and monitoring
- Health check with auto-restart for sentinels
- Process status reporting (PID, alive, uptime, crash count)
- Project registration and configuration
- Systemd user-level service unit for set-manager
- CLI for service management (serve, start, stop, status)

### Out of scope
- Orchestrator auto-restart (always notify, never auto-restart)
- Multi-machine deployment
- Container-based isolation
- Dynamic systemd unit creation per sentinel

## Requirements

### Requirement: Sentinel lifecycle management
The supervisor SHALL spawn sentinel agents as claude CLI subprocesses for registered projects. It SHALL track PIDs and monitor health via `is_alive()` checks every tick.

#### Scenario: Start sentinel
- **WHEN** user requests sentinel start for project "craftbrew-run12"
- **THEN** a claude agent process is spawned with the sentinel prompt, PID is recorded, started_at is set

#### Scenario: Stop sentinel
- **WHEN** user requests sentinel stop
- **THEN** the sentinel process is gracefully killed and PID is cleared

### Requirement: Sentinel auto-restart
The supervisor SHALL auto-restart crashed sentinels if `auto_restart_sentinel` is enabled for the project. It SHALL track crash_count and use exponential backoff (max 5 restarts before stopping and alerting).

#### Scenario: Sentinel crash detected
- **WHEN** health check finds sentinel PID is no longer alive and auto_restart is enabled
- **THEN** a new sentinel is spawned, crash_count is incremented, and an event is logged

#### Scenario: Restart limit reached
- **WHEN** sentinel crashes for the 6th time (exceeding max 5 restarts)
- **THEN** auto-restart stops, a critical notification is sent, and sentinel stays stopped

### Requirement: Orchestration management
The supervisor SHALL start orchestrations via the existing `set-orchestrate` command and monitor the process. It SHALL NOT auto-restart orchestrations — only notify on crash.

#### Scenario: Start orchestration
- **WHEN** user requests orchestration start for a project
- **THEN** `set-orchestrate` is spawned as subprocess, PID is tracked

#### Scenario: Orchestrator crash
- **WHEN** orchestrator PID dies
- **THEN** a critical notification is sent but no auto-restart happens

### Requirement: Project registry
The supervisor SHALL maintain a registry of projects with name, path, mode (e2e/production/development), and sentinel settings. Projects SHALL be addable/removable via CLI and API.

#### Scenario: Register project
- **WHEN** `set-manager project add craftbrew-run12 /path/to/project --mode e2e`
- **THEN** project is added to config and sentinel can be started for it

### Requirement: Service lifecycle
The set-manager service SHALL run as a systemd user-level unit. It SHALL provide CLI commands: `set-manager serve` (foreground), `set-manager start` (enable+start systemd), `set-manager stop`, `set-manager status`.

#### Scenario: Service auto-restart
- **WHEN** set-manager process crashes
- **THEN** systemd restarts it within 5 seconds and all supervised processes resume monitoring

#### Scenario: Service status
- **WHEN** `set-manager status` is run
- **THEN** it shows service health, uptime, and status of all projects with their sentinel/orchestrator PIDs

# Manager REST API

## ADDED Requirements

## IN SCOPE
- Project management endpoints (list, register, status)
- Sentinel and orchestration control endpoints (start, stop, restart)
- Issue CRUD and action endpoints
- Group and mute pattern endpoints
- Audit log and stats endpoints
- Cross-project aggregated endpoints
- Service health endpoint

## OUT OF SCOPE
- Authentication/authorization (local service, no auth)
- WebSocket endpoints (chat goes through set-web's existing chat.py)
- GraphQL (REST only)
- API versioning (v1 implicit)

### Requirement: Project endpoints
The API SHALL provide endpoints to list all projects with status, register new projects, and get detailed project status including sentinel/orchestrator PIDs and issue stats.

#### Scenario: List projects with status
- **WHEN** GET /api/projects is called
- **THEN** all registered projects are returned with sentinel/orchestrator alive status and issue counts

#### Scenario: Register project
- **WHEN** POST /api/projects is called with name, path, mode
- **THEN** the project is added to the registry and sentinel can be started

### Requirement: Process control endpoints
The API SHALL provide endpoints to start, stop, and restart sentinels and orchestrations per project.

#### Scenario: Start sentinel via API
- **WHEN** POST /api/projects/craftbrew-run12/sentinel/start is called
- **THEN** a sentinel agent is spawned and the response includes the new PID

#### Scenario: Stop orchestration via API
- **WHEN** POST /api/projects/craftbrew-run12/orchestration/stop is called
- **THEN** the orchestrator process is killed and status updated

### Requirement: Issue action endpoints
The API SHALL provide action endpoints that trigger state transitions: investigate, fix, dismiss, cancel, skip, mute, extend-timeout. Each action SHALL validate the transition and return an error if the transition is invalid for the current state.

#### Scenario: Fix action
- **WHEN** POST /api/projects/{name}/issues/ISS-001/fix is called
- **THEN** the issue transitions to FIXING (or is queued if another fix is running)

#### Scenario: Invalid action rejected
- **WHEN** POST /api/projects/{name}/issues/ISS-001/fix is called but ISS-001 is in NEW state
- **THEN** HTTP 409 is returned (can't fix without investigation/diagnosis)

### Requirement: Issue listing with filters
The API SHALL support listing issues with optional filters: state, severity, source. Results SHALL be sorted by detected_at descending.

#### Scenario: Filter by severity
- **WHEN** GET /api/projects/{name}/issues?severity=high is called
- **THEN** only high severity issues are returned

### Requirement: Cross-project endpoints
The API SHALL provide endpoints that aggregate issues and stats across all registered projects.

#### Scenario: All issues across projects
- **WHEN** GET /api/issues is called
- **THEN** issues from all projects are returned with environment field for grouping

### Requirement: Audit log endpoint
The API SHALL provide an endpoint to retrieve the audit trail with optional since/limit parameters.

#### Scenario: Recent audit entries
- **WHEN** GET /api/projects/{name}/issues/audit?limit=50 is called
- **THEN** the 50 most recent audit entries are returned

### Requirement: Service health
The API SHALL provide a health endpoint showing service uptime, tick interval, and overall status.

#### Scenario: Health check
- **WHEN** GET /api/manager/status is called
- **THEN** uptime, tick interval, and project count are returned

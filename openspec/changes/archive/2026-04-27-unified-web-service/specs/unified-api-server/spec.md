# Capability: Unified API Server

## ADDED Requirements

## IN SCOPE
- Single FastAPI application hosting all API routes (orchestration, sentinel, issues)
- SPA static file serving from the same process
- Background supervisor and issue engine tick loops
- Single project registry from projects.json
- Single CLI entry point (`set-core serve`)
- Deprecation of set-manager and set-orch-core CLIs

## OUT OF SCOPE
- Changes to orchestration engine internals (engine.py, merger.py, verifier.py, dispatcher.py)
- Changes to issue engine logic (models.py, state machine, policy)
- Changes to SPA frontend components or routes
- Multi-process or microservice architecture

### Requirement: API module package structure
The server SHALL organize API routes into a `lib/set_orch/api/` package with domain-based modules: projects, orchestration, sessions, sentinel, issues, actions, media, plugins.

#### Scenario: Import and route registration
- **WHEN** the server starts
- **THEN** all domain routers are registered on the FastAPI app and all existing API endpoints remain accessible at the same paths

### Requirement: Sentinel routes in unified server
The server SHALL expose sentinel control routes (`/api/{project}/sentinel/start`, `stop`, `restart`, `log`) previously served by the manager's aiohttp API.

#### Scenario: Sentinel start via unified API
- **WHEN** a POST request is sent to `/api/{project}/sentinel/start`
- **THEN** the supervisor spawns a sentinel process for that project and returns success status

#### Scenario: Sentinel log retrieval
- **WHEN** a GET request is sent to `/api/{project}/sentinel/log`
- **THEN** the server returns the sentinel's stdout/stderr log lines

### Requirement: Issue routes in unified server
The server SHALL expose issue management routes (`/api/{project}/issues/*`) previously served by the manager's aiohttp API, including CRUD, actions, groups, mutes, audit, and stats.

#### Scenario: List issues
- **WHEN** a GET request is sent to `/api/{project}/issues`
- **THEN** the server returns all issues for that project from the issue registry

#### Scenario: Issue action
- **WHEN** a POST request is sent to `/api/{project}/issues/{id}/investigate`
- **THEN** the issue manager executes the action and returns updated issue state

### Requirement: Unified project registry
The server SHALL read projects exclusively from `~/.config/set-core/projects.json`. The manager's separate config.yaml project registry SHALL be eliminated.

#### Scenario: Project registered via API appears in list
- **WHEN** a project is added via `POST /api/projects`
- **THEN** it is persisted to projects.json and immediately visible in `GET /api/projects` with orchestration state, sentinel status, and issue stats

### Requirement: Background supervisor lifecycle
The server SHALL run the supervisor tick loop (sentinel health checks, issue detection, issue engine ticks) as a background async task within the FastAPI process.

#### Scenario: Supervisor runs on startup
- **WHEN** the server starts with registered projects
- **THEN** the supervisor tick loop begins polling sentinel health and running issue manager ticks at the configured interval

#### Scenario: Supervisor survives exceptions
- **WHEN** a supervisor tick throws an exception
- **THEN** the error is logged and the tick loop continues on the next interval

### Requirement: Single CLI entry point
`set-core serve` SHALL start the unified server. `set-orch-core serve` and `set-manager serve` SHALL print deprecation warnings directing users to `set-core serve`.

#### Scenario: set-core serve starts unified server
- **WHEN** user runs `set-core serve --port 7400`
- **THEN** the unified FastAPI server starts, hosting SPA, all API routes, and background supervisor

#### Scenario: Deprecated CLI warns
- **WHEN** user runs `set-manager serve`
- **THEN** a deprecation warning is printed and the command either exits or delegates to `set-core serve`

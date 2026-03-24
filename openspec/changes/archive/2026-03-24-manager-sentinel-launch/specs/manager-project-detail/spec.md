# Capability: manager-project-detail

## ADDED Requirements

## IN SCOPE
- Project detail page at `/manager/:project` route
- Docs directory listing from project path
- Sentinel control with spec path selection (dropdown/autocomplete)
- Orchestration status display (from orchestration-state.json if exists)
- Issues summary with link to existing issues page
- Navigation back to tile overview

## OUT OF SCOPE
- Editing docs files from the UI
- Creating new projects from the UI (use `set-project init` CLI)
- Real-time log streaming from sentinel stdout
- Orchestration Gantt chart or token graphs (future)
- Changes list visualization (future — separate change)

### Requirement: Project detail page route

The system SHALL serve a project detail page at `/manager/:project` that displays project name, mode, path, and current process status.

#### Scenario: Navigate to project detail
- **WHEN** user clicks a project tile on the manager overview
- **THEN** browser navigates to `/manager/:project` showing the detail view

#### Scenario: Direct URL access
- **WHEN** user navigates directly to `/manager/craftbrew`
- **THEN** the detail view loads for project "craftbrew" with all sections populated

#### Scenario: Project not found
- **WHEN** user navigates to `/manager/nonexistent`
- **THEN** the page displays an error message indicating the project was not found

### Requirement: Docs directory listing

The system SHALL display the contents of the project's `docs/` directory, showing file names and subdirectory structure.

#### Scenario: Project has docs
- **WHEN** the detail page loads for a project with `docs/catalog/coffees.md` and `docs/features/cart.md`
- **THEN** the Docs section displays the file tree grouped by subdirectory

#### Scenario: Project has no docs
- **WHEN** the detail page loads for a project with no `docs/` directory
- **THEN** the Docs section displays a message indicating no docs found

### Requirement: Docs listing API endpoint

The manager API SHALL expose `GET /api/projects/{name}/docs` returning a list of files and directories under the project's `docs/` path.

#### Scenario: List docs for project
- **WHEN** client sends `GET /api/projects/craftbrew/docs`
- **THEN** response contains `{"docs": [{"path": "docs/catalog/coffees.md", "type": "file"}, {"path": "docs/catalog/", "type": "dir"}, ...]}`

#### Scenario: List docs for project without docs directory
- **WHEN** client sends `GET /api/projects/craftbrew/docs` and no `docs/` exists
- **THEN** response contains `{"docs": []}`

### Requirement: Sentinel control with spec selection

The detail page SHALL provide a sentinel control panel with a spec path input (dropdown/autocomplete populated from docs subdirectories) and Start/Stop/Restart buttons.

#### Scenario: Start sentinel with spec path
- **WHEN** user selects "docs/" from the spec dropdown and clicks Start
- **THEN** system calls `POST /api/projects/{name}/sentinel/start` with `{"spec": "docs/"}` and sentinel process starts

#### Scenario: Spec autocomplete from docs
- **WHEN** user types "docs/cat" in the spec input
- **THEN** autocomplete suggests "docs/catalog/" based on the docs listing

#### Scenario: Stop running sentinel
- **WHEN** sentinel is running and user clicks Stop
- **THEN** system calls the stop endpoint and UI reflects idle state

### Requirement: Orchestration status display

The detail page SHALL display current orchestration status when an `orchestration-state.json` exists in the project directory, showing overall status, change count, and token usage.

#### Scenario: Active orchestration
- **WHEN** the project has an orchestration-state.json with status "running" and 5 changes
- **THEN** the status section shows "Running — 3/5 merged, 1.2M tokens"

#### Scenario: No orchestration
- **WHEN** the project has no orchestration-state.json
- **THEN** the status section shows "No orchestration data"

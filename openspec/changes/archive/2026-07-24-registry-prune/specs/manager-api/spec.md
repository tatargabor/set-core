## MODIFIED Requirements

### Requirement: Project endpoints
The API SHALL provide endpoints to list all projects with status, register new projects, and
get detailed project status including sentinel/orchestrator PIDs and issue stats. The list
endpoint SHALL omit entries marked archived in the registry unless the caller asks for them,
and SHALL report how many were omitted so the omission is never silent.

#### Scenario: List projects with status
- **WHEN** GET /api/projects is called
- **THEN** all registered non-archived projects are returned with sentinel/orchestrator alive
  status and issue counts

#### Scenario: Archived projects are omitted but counted
- **WHEN** GET /api/projects is called and some registry entries are archived
- **THEN** those entries are absent from the returned list and the response reports the number
  omitted

#### Scenario: Archived projects on request
- **WHEN** GET /api/projects?include_archived=true is called
- **THEN** archived entries are returned as well, each marked as archived

#### Scenario: Register project
- **WHEN** POST /api/projects is called with name, path, mode
- **THEN** the project is added to the registry and sentinel can be started

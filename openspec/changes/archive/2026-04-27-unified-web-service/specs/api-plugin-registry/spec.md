# Capability: API Plugin Registry

## ADDED Requirements

## IN SCOPE
- Entry_points-based API route discovery and registration
- Plugin routes mounted under project-scoped paths
- Plugin registration at server startup

## OUT OF SCOPE
- Plugin UI/frontend chunk serving (future work)
- Plugin authentication or authorization
- Hot-reloading plugins at runtime

### Requirement: Plugin route discovery
The server SHALL discover API route plugins via the `set_core.api_routes` entry_points group at startup.

#### Scenario: Plugin with registered entry_point
- **WHEN** a package is installed with `[project.entry-points."set_core.api_routes"]` containing a `register_routes` callable
- **THEN** the server calls `register_routes(router)` during startup and the plugin's routes become accessible

### Requirement: Plugin route registration interface
Each plugin SHALL provide a `register_routes(router: APIRouter)` function that adds routes to the provided FastAPI router.

#### Scenario: Plugin adds project-scoped route
- **WHEN** a plugin registers `@router.get("/api/{project}/voice/calls")`
- **THEN** the route is accessible at that path and receives the project parameter

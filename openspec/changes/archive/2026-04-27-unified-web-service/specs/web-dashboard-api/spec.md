# Capability: Web Dashboard API (delta)

## MODIFIED Requirements

### Requirement: API route organization
The web dashboard API SHALL be organized into domain-based modules under `lib/set_orch/api/` instead of a single monolithic `api.py` file. All existing API endpoints SHALL remain at the same paths with the same request/response formats.

#### Scenario: Existing orchestration routes unchanged
- **WHEN** a client calls any existing `/api/{project}/state`, `/api/{project}/changes/*`, or `/api/{project}/sessions/*` endpoint
- **THEN** the response format and status codes are identical to the pre-refactor behavior

#### Scenario: Project list includes all data sources
- **WHEN** a client calls `GET /api/projects`
- **THEN** each project includes orchestration state (changes, tokens, duration), sentinel status, and issue stats from a single unified response

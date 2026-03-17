## ADDED Requirements

### Requirement: Coverage report endpoint
The server SHALL expose `GET /api/{project}/coverage-report` which reads and returns the content of `wt/orchestration/spec-coverage-report.md` from the project directory.

#### Scenario: Report file exists
- **WHEN** the file `wt/orchestration/spec-coverage-report.md` exists in the resolved project path
- **THEN** the endpoint returns `{"exists": true, "content": "<file content>"}` with HTTP 200

#### Scenario: Report file missing
- **WHEN** the file does not exist
- **THEN** the endpoint returns `{"exists": false}` with HTTP 200

#### Scenario: Invalid project
- **WHEN** the project name cannot be resolved
- **THEN** the endpoint returns HTTP 404

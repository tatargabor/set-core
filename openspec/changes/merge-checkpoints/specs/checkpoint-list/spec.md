## ADDED Requirements

## IN SCOPE
- API endpoint to list checkpoints for a project
- CLI output for listing checkpoints (used by recovery skill)
- Returning structured data: change name, commit SHA, phase, timestamp, merged count

## OUT OF SCOPE
- Web UI components (handled in tasks, not spec'd here — simple table rendering)
- Checkpoint deletion/pruning API
- Filtering or searching checkpoints

### Requirement: List checkpoints API
The system SHALL provide a GET endpoint at `/api/{project}/checkpoints` that returns all checkpoint records from the manifest JSONL, ordered by sequence (oldest first).

#### Scenario: Project with checkpoints
- **WHEN** a GET request is made to `/api/myproject/checkpoints`
- **AND** `myproject` has 3 merged changes with checkpoints
- **THEN** the response is a JSON array of 3 checkpoint records, each containing `change`, `sha`, `phase`, `ts`, and `merged_so_far`

#### Scenario: Project with no checkpoints
- **WHEN** a GET request is made to `/api/myproject/checkpoints`
- **AND** the manifest file does not exist
- **THEN** the response is an empty JSON array `[]`

#### Scenario: Corrupted manifest line
- **WHEN** the manifest JSONL contains a malformed line
- **THEN** that line is skipped and valid records are still returned

### Requirement: List checkpoints from Python
The system SHALL provide a `list_checkpoints(project_path)` function in the recovery or checkpoint module that parses the manifest JSONL and returns a list of checkpoint dicts.

#### Scenario: Programmatic access
- **WHEN** `list_checkpoints(Path("/path/to/project"))` is called
- **THEN** it returns a list of dicts parsed from `set/orchestration/checkpoints/manifest.jsonl`

#### Scenario: Used by recovery skill
- **WHEN** the recovery skill needs to display available restore points
- **THEN** it calls `list_checkpoints()` and renders a table with change name, phase, date, and commit SHA

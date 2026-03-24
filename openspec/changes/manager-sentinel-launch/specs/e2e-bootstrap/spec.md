# Capability: e2e-bootstrap

## ADDED Requirements

## IN SCOPE
- Shell script to bootstrap an E2E test run from a scaffold
- Create project directory, git init, copy scaffold docs
- Run `set-project init` with appropriate project type
- Register project with manager API
- Start sentinel via manager API with spec path
- Print monitor URL for web dashboard

## OUT OF SCOPE
- Post-run result collection (separate `set-e2e-collect` — future)
- Comparing results across runs (future)
- Creating new scaffold fixtures (manual process)
- Running without a manager (direct claude -p fallback)

### Requirement: E2E bootstrap script

The system SHALL provide `tests/e2e/run.sh` that creates a complete E2E test run from a scaffold name.

#### Scenario: Bootstrap craftbrew run
- **WHEN** user runs `./tests/e2e/run.sh craftbrew`
- **THEN** the script creates a new directory under `~/.local/share/set-core/e2e-runs/craftbrew-run<N>`, initializes git, copies `tests/e2e/scaffolds/craftbrew/docs/` into it, runs `set-project init --project-type web`, and outputs the run directory path

### Requirement: Manager API registration

The bootstrap script SHALL register the new project with the running manager via `POST /api/projects`.

#### Scenario: Register with manager
- **WHEN** the bootstrap script has initialized the project directory
- **THEN** it sends `POST /api/projects` with `{"name": "<run-name>", "path": "<run-dir>", "mode": "e2e"}` and verifies a 200 response

#### Scenario: Manager not running
- **WHEN** the manager API is not reachable
- **THEN** the script prints an error and exits with non-zero code

### Requirement: Sentinel start via API

The bootstrap script SHALL start the sentinel via `POST /api/projects/{name}/sentinel/start` with the spec path.

#### Scenario: Start sentinel after registration
- **WHEN** the project is registered with the manager
- **THEN** the script sends `POST /api/projects/{name}/sentinel/start` with `{"spec": "docs/"}` and prints the monitor URL

### Requirement: Run naming with auto-increment

The bootstrap script SHALL auto-increment run numbers per scaffold name.

#### Scenario: First run for scaffold
- **WHEN** no previous runs exist for scaffold "craftbrew"
- **THEN** the run is named "craftbrew-run1"

#### Scenario: Subsequent run
- **WHEN** "craftbrew-run1" through "craftbrew-run8" already exist
- **THEN** the new run is named "craftbrew-run9"

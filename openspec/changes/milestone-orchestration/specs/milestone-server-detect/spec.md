## ADDED Requirements

### Requirement: Auto-detect dev server command
The orchestrator SHALL auto-detect the project's dev server command by checking project files in priority order. The detected command SHALL be used for milestone worktree dev servers.

#### Scenario: Next.js or Vite project (npm)
- **WHEN** `package.json` exists with a `scripts.dev` entry and no `bun.lockb`
- **THEN** dev server command SHALL be `npm run dev`

#### Scenario: Bun project
- **WHEN** `package.json` exists with `scripts.dev` and `bun.lockb` exists
- **THEN** dev server command SHALL be `bun run dev`

#### Scenario: Docker Compose project
- **WHEN** `docker-compose.yml` or `compose.yml` exists (and no package.json with scripts.dev)
- **THEN** dev server command SHALL be `docker compose up`

#### Scenario: Makefile project
- **WHEN** `Makefile` exists with a `dev` or `serve` target (and no higher-priority match)
- **THEN** dev server command SHALL be `make dev` or `make serve` (first match)

#### Scenario: Django project
- **WHEN** `manage.py` exists (and no higher-priority match)
- **THEN** dev server command SHALL be `python manage.py runserver`

#### Scenario: No server detected
- **WHEN** none of the above files/patterns match
- **THEN** detection SHALL return empty string and log a warning

### Requirement: Manual override via orchestration.yaml
Users SHALL be able to override auto-detection by setting `milestones.dev_server` in orchestration.yaml.

#### Scenario: Explicit override
- **WHEN** `milestones.dev_server` is set to `"yarn dev"`
- **THEN** auto-detection SHALL be skipped and `yarn dev` SHALL be used

#### Scenario: Override disables server
- **WHEN** `milestones.dev_server` is set to `"none"` or `"false"`
- **THEN** no dev server SHALL be started for milestones

### Requirement: Port assignment
Each milestone dev server SHALL receive a unique port via `PORT` environment variable. Port is calculated as `milestones.base_port` (default: 3100) plus the phase number.

#### Scenario: Port calculation
- **WHEN** base_port is 3100 and phase is 2
- **THEN** `PORT=3102` SHALL be set in the server's environment

#### Scenario: Custom base port
- **WHEN** `milestones.base_port` is set to 4000
- **THEN** phase 1 server SHALL use port 4001, phase 2 SHALL use port 4002, etc.

### Requirement: Dependency installation before server start
Before starting the dev server in a milestone worktree, the orchestrator SHALL run dependency installation if detected (same detection logic as server command).

#### Scenario: Node.js dependency install
- **WHEN** `package.json` exists in the milestone worktree
- **THEN** `npm install` (or `bun install`) SHALL run before `npm run dev`
- **AND** installation failure SHALL be logged as warning but not block the checkpoint

#### Scenario: No dependencies
- **WHEN** no package manager lockfile or requirements file exists
- **THEN** server SHALL be started directly without install step

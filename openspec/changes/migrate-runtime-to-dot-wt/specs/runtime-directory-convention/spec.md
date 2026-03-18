## ADDED Requirements

## IN SCOPE
- `.wt/` directory as single location for all runtime/ephemeral data
- Subdirectory layout: orchestration/, agent/, logs/, cache/
- Central path resolution via Python config constant
- `.gitignore` simplification (single `/.wt/` entry)
- Migration of all existing runtime files to new locations
- Backward-compatible bootstrap (wt-project init, bootstrap_worktree)

## OUT OF SCOPE
- Changing the behavior of any runtime file (only paths change)
- Removing the `.claude/` directory (it keeps config: settings, commands, skills, rules, hooks, agents)
- Sentinel-specific files (already handled by sentinel-tab change)
- Changing `wt/orchestration/config.yaml` location (config stays in `wt/`)
- Changing `wt/orchestration/specs/` location (specs are artifacts, not runtime)
- Changing `wt/orchestration/digest/` location (digest output is a valuable artifact)

### Requirement: Centralized runtime directory
The system SHALL use `.wt/` in the project root as the single directory for all runtime and ephemeral data, gitignored with a single `/.wt/` entry.

#### Scenario: Directory created on first use
- **WHEN** any wt-tools component needs to write runtime data and `.wt/` does not exist
- **THEN** it SHALL create `.wt/` with the required subdirectory and ensure `/.wt/` is in `.gitignore`

### Requirement: Orchestration runtime migration
The system SHALL store orchestration runtime files under `.wt/orchestration/` instead of their current scattered locations.

#### Scenario: State file at new path
- **WHEN** the orchestration engine reads or writes the state file
- **THEN** it SHALL use `.wt/orchestration/state.json` (migrated from `wt/orchestration/orchestration-state.json`)

#### Scenario: Events file at new path
- **WHEN** the orchestration engine appends events
- **THEN** it SHALL use `.wt/orchestration/events.jsonl` (migrated from `orchestration-events.jsonl` in project root)

#### Scenario: Plans and runs at new path
- **WHEN** the planner writes plan files or run logs
- **THEN** it SHALL use `.wt/orchestration/plans/` and `.wt/orchestration/runs/` (migrated from `wt/orchestration/plans/` and `wt/orchestration/runs/`)

### Requirement: Agent runtime migration
The system SHALL store agent loop runtime files under `.wt/agent/` instead of `.claude/`.

#### Scenario: Loop state at new path
- **WHEN** the ralph loop reads or writes loop state
- **THEN** it SHALL use `.wt/agent/loop-state.json` (migrated from `.claude/loop-state.json`)

#### Scenario: Activity file at new path
- **WHEN** agent activity is recorded
- **THEN** it SHALL use `.wt/agent/activity.json` (migrated from `.claude/activity.json`)

#### Scenario: PID files at new path
- **WHEN** sentinel or ralph PID files are written
- **THEN** they SHALL use `.wt/agent/sentinel.pid` and `.wt/agent/ralph-terminal.pid` (migrated from `.claude/`)

### Requirement: Log migration
The system SHALL store all logs under `.wt/logs/`.

#### Scenario: Orchestration log at new path
- **WHEN** orchestration events are logged
- **THEN** the log SHALL be written to `.wt/logs/orchestration.log` (migrated from `.claude/orchestration.log`)

#### Scenario: Ralph iteration logs at new path
- **WHEN** ralph loop iteration logs are written
- **THEN** they SHALL be written to `.wt/logs/ralph-iter-*.log` (migrated from `.claude/logs/`)

### Requirement: Cache migration
The system SHALL store caches under `.wt/cache/` instead of `.wt-tools/`.

#### Scenario: Codemap cache at new path
- **WHEN** codemaps are cached
- **THEN** they SHALL be stored under `.wt/cache/codemaps/` (migrated from `.wt-tools/.saved-codemaps`)

#### Scenario: Design cache at new path
- **WHEN** design metadata is cached
- **THEN** it SHALL be stored under `.wt/cache/designs/` (migrated from `.wt-tools/.saved-designs`)

### Requirement: Design snapshot migration
The system SHALL store the design snapshot under `.wt/` instead of project root.

#### Scenario: Design snapshot at new path
- **WHEN** the design bridge fetches a design snapshot
- **THEN** it SHALL write to `.wt/design-snapshot.md` (migrated from `design-snapshot.md` in project root)

### Requirement: Path resolution via config constant
All runtime file access SHALL go through a centralized path resolution constant or function, not hardcoded relative paths.

#### Scenario: Python code uses WtDirs
- **WHEN** Python code needs a runtime file path
- **THEN** it SHALL use `WtDirs(project_path).state_file`, `WtDirs.events_file(project_path)`, etc. instead of string concatenation

#### Scenario: Bash code uses wt-paths helper
- **WHEN** bash code needs a runtime file path
- **THEN** it SHALL use a `wt-paths` helper function or source a paths config instead of hardcoded paths

### Requirement: Gitignore simplification
The `.gitignore` SHALL use a single `/.wt/` entry to cover all runtime files.

#### Scenario: Old scattered patterns removable
- **WHEN** migration is complete
- **THEN** the following `.gitignore` patterns SHALL be removable: `loop-state.json`, `activity.json`, `*.pid`, `.claude/logs/`, `.claude/orchestration.log`, `orchestration-events.jsonl`, `.wt-tools/`

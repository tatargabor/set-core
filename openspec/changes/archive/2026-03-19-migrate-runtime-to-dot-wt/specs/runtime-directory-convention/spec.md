## ADDED Requirements

## IN SCOPE
- `~/.local/share/wt-tools/<project>/` as location for all shared runtime data (worktree-independent)
- `<worktree>/.wt/` as minimal location for per-agent ephemeral data only
- Subdirectory layout: orchestration/, sentinel/, logs/, cache/, screenshots/
- Central path resolution via Python `WtRuntime` class and bash `wt-paths` helper
- `.gitignore` simplification (remove scattered patterns, keep only `/.wt/` for per-worktree)
- Migration of all existing runtime files to new locations
- Sentinel migration from project-local `.wt/sentinel/` to shared location
- Backward-compatible bootstrap (wt-project init auto-migration)
- Worktree retention after merge (configurable, default: keep)

## OUT OF SCOPE
- Changing the behavior of any runtime file (only paths change)
- Removing the `.claude/` directory (it keeps config: settings, commands, skills, rules, hooks, agents)
- Changing `wt/orchestration/orchestration.yaml` location (config stays in `wt/`)
- Changing `wt/orchestration/specs/` location (specs are artifacts, not runtime)
- Moving memory or metrics (already in `~/.local/share/wt-tools/`)
- Moving daemon PID/socket from `/tmp/` (OS convention)

### Requirement: Shared runtime directory
The system SHALL use `~/.local/share/wt-tools/<project>/` (respecting `XDG_DATA_HOME`) as the location for all shared runtime data. Project name SHALL be resolved from git repo name, consistent with the memory system.

#### Scenario: Directory created on first use
- **WHEN** any wt-tools component needs to write shared runtime data and the directory does not exist
- **THEN** it SHALL create the required subdirectory under `~/.local/share/wt-tools/<project>/`

#### Scenario: Worktree-independence
- **WHEN** multiple worktrees exist for the same project
- **THEN** they SHALL all resolve to the same shared runtime directory

### Requirement: Per-worktree agent ephemeral
The system SHALL use `<worktree>/.wt/` for per-agent ephemeral data only: loop-state.json, activity.json, PID files, current iteration logs.

#### Scenario: Agent writes to worktree-local path
- **WHEN** an agent writes loop state or activity during execution
- **THEN** it SHALL write to `<worktree>/.wt/loop-state.json` and `<worktree>/.wt/activity.json`

### Requirement: Orchestration runtime migration
The system SHALL store orchestration runtime files under the shared `orchestration/` subdirectory.

#### Scenario: State file at new path
- **WHEN** the orchestration engine reads or writes the state file
- **THEN** it SHALL use `~/.local/share/wt-tools/<project>/orchestration/state.json`

#### Scenario: Events file at new path
- **WHEN** the orchestration engine appends events
- **THEN** it SHALL use `~/.local/share/wt-tools/<project>/orchestration/events.jsonl`

#### Scenario: Plans, runs, digest at new path
- **WHEN** the planner writes plan files, run logs, or digest cache
- **THEN** it SHALL use subdirectories under `~/.local/share/wt-tools/<project>/orchestration/`

#### Scenario: Screenshots at new path
- **WHEN** smoke or e2e screenshots are captured
- **THEN** they SHALL be stored under `~/.local/share/wt-tools/<project>/screenshots/`

### Requirement: Sentinel migration
The system SHALL move sentinel runtime files from project-local `.wt/sentinel/` to the shared `sentinel/` subdirectory.

#### Scenario: Sentinel events at shared path
- **WHEN** sentinel writes events, findings, status, or inbox
- **THEN** it SHALL use `~/.local/share/wt-tools/<project>/sentinel/`

#### Scenario: Sentinel PID at shared path
- **WHEN** sentinel writes its PID file
- **THEN** it SHALL use `~/.local/share/wt-tools/<project>/sentinel/sentinel.pid` (migrated from project root `sentinel.pid`)

### Requirement: Agent runtime migration
The system SHALL store agent loop runtime files under `<worktree>/.wt/` instead of `<worktree>/.claude/`.

#### Scenario: Loop state at new path
- **WHEN** the ralph loop reads or writes loop state
- **THEN** it SHALL use `<worktree>/.wt/loop-state.json`

#### Scenario: Activity file at new path
- **WHEN** agent activity is recorded
- **THEN** it SHALL use `<worktree>/.wt/activity.json`

#### Scenario: PID files at new path
- **WHEN** ralph PID files are written
- **THEN** they SHALL use `<worktree>/.wt/ralph-terminal.pid`

### Requirement: Log migration
The system SHALL store logs under the shared `logs/` subdirectory and per-worktree `.wt/logs/`.

#### Scenario: Orchestration log at shared path
- **WHEN** orchestration events are logged
- **THEN** the log SHALL be written to `~/.local/share/wt-tools/<project>/logs/orchestration.log`

#### Scenario: Current iteration logs at worktree path
- **WHEN** ralph loop writes iteration logs during execution
- **THEN** they SHALL be written to `<worktree>/.wt/logs/ralph-iter-*.log`

#### Scenario: Archived iteration logs at shared path
- **WHEN** a change is merged and logs are archived
- **THEN** iteration logs SHALL be copied to `~/.local/share/wt-tools/<project>/logs/changes/{change-name}/`

### Requirement: Cache migration
The system SHALL store caches under the shared `cache/` subdirectory.

#### Scenario: Codemap cache at new path
- **WHEN** codemaps are cached
- **THEN** they SHALL be stored under `~/.local/share/wt-tools/<project>/cache/codemaps/`

#### Scenario: Design cache at new path
- **WHEN** design metadata is cached
- **THEN** it SHALL be stored under `~/.local/share/wt-tools/<project>/cache/designs/`

#### Scenario: Credentials at new path
- **WHEN** service credentials (jira, confluence) are stored
- **THEN** they SHALL be under `~/.local/share/wt-tools/<project>/cache/credentials/`

### Requirement: Design snapshot migration
The system SHALL store the design snapshot under the shared runtime directory.

#### Scenario: Design snapshot at new path
- **WHEN** the design bridge fetches a design snapshot
- **THEN** it SHALL write to `~/.local/share/wt-tools/<project>/design-snapshot.md`

### Requirement: Path resolution via config constant
All runtime file access SHALL go through a centralized path resolution mechanism.

#### Scenario: Python code uses WtRuntime
- **WHEN** Python code needs a shared runtime file path
- **THEN** it SHALL use `WtRuntime(project_path).state_file`, `.events_file`, etc.

#### Scenario: Python code uses WtRuntime.agent_dir
- **WHEN** Python code needs a per-worktree agent path
- **THEN** it SHALL use `WtRuntime.agent_dir(worktree_path)` to resolve `<worktree>/.wt/`

#### Scenario: Bash code uses wt-paths helper
- **WHEN** bash code needs a runtime file path
- **THEN** it SHALL source `wt-paths` and use exported variables

### Requirement: Gitignore simplification
The `.gitignore` SHALL be simplified by removing scattered runtime patterns.

#### Scenario: Old scattered patterns removable
- **WHEN** migration is complete
- **THEN** the following `.gitignore` patterns SHALL be removable: `loop-state.json`, `activity.json`, `*.pid`, `.claude/logs/`, `.claude/orchestration.log`, `orchestration-events.jsonl`, `.wt-tools/`
- **AND** only `/.wt/` SHALL remain for per-worktree ephemeral files

### Requirement: Worktree retention
The system SHALL support configurable worktree lifecycle after merge.

#### Scenario: Retention keep (default)
- **WHEN** a change is merged and `worktree_retention` is `keep`
- **THEN** the worktree directory and branch SHALL be preserved
- **AND** logs SHALL still be archived to the shared location

#### Scenario: Retention delete-on-merge
- **WHEN** a change is merged and `worktree_retention` is `delete-on-merge`
- **THEN** the worktree directory and branch SHALL be deleted after log archival (legacy behavior)

#### Scenario: Manual cleanup
- **WHEN** `wt-cleanup --older-than Nd` is run
- **THEN** worktrees for changes merged more than N days ago SHALL be removed

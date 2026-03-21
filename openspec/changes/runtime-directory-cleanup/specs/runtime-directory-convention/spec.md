## MODIFIED Requirements

### Requirement: Runtime root includes runtime/ subdirectory
The `SetRuntime` class SHALL resolve the per-project runtime root as `~/.local/share/set-core/runtime/<project-name>/` instead of `~/.local/share/set-core/<project-name>/`.

#### Scenario: New project runtime path
- **WHEN** `SetRuntime("craftbrew-run7")` is instantiated
- **THEN** `root` is `~/.local/share/set-core/runtime/craftbrew-run7/`

#### Scenario: Bash equivalent
- **WHEN** `set-paths` is sourced for project `craftbrew-run7`
- **THEN** `WT_RUNTIME_DIR` is `~/.local/share/set-core/runtime/craftbrew-run7/`

### Requirement: Auto-migration of legacy runtime directories
When `SetRuntime` initializes and the old-style directory exists (`~/.local/share/set-core/<project>/`) but the new-style does not (`~/.local/share/set-core/runtime/<project>/`), the system SHALL move the old directory to the new location automatically.

#### Scenario: First access after upgrade
- **WHEN** `~/.local/share/set-core/craftbrew-run7/` exists
- **AND** `~/.local/share/set-core/runtime/craftbrew-run7/` does not exist
- **THEN** the directory is moved to `~/.local/share/set-core/runtime/craftbrew-run7/`

#### Scenario: Already migrated
- **WHEN** `~/.local/share/set-core/runtime/craftbrew-run7/` already exists
- **THEN** no migration occurs

### Requirement: Watcher discovers paths via SetRuntime
The watcher SHALL use `SetRuntime` to discover state and log file paths instead of hardcoding `wt/orchestration/` or project-root relative paths. Legacy fallback paths SHALL remain for backward compatibility.

#### Scenario: State file discovery
- **WHEN** the watcher looks for a project's state file
- **THEN** it checks `SetRuntime(project_path).state_file` first
- **AND** falls back to project-local legacy paths if not found

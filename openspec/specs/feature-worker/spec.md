# Feature Worker Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: FeatureWorker background thread
A `FeatureWorker(QThread)` SHALL poll per-project feature status (memory and openspec) in a background thread. The poll interval SHALL be 15 seconds (configurable). Results SHALL be stored in a dict keyed by project name and emitted via a `features_updated` signal.

#### Scenario: Normal polling cycle
- **WHEN** the FeatureWorker timer fires
- **THEN** it iterates all known projects, runs `set-memory status --json --project X` and `set-openspec status --json` (with cwd set to main repo), parses results, and emits `features_updated` with the combined dict

#### Scenario: Worker startup
- **WHEN** the ControlCenter window initializes
- **THEN** the FeatureWorker starts and runs its first poll immediately

#### Scenario: Subprocess failure
- **WHEN** a subprocess call times out or fails
- **THEN** the worker returns default values (`{"available": false, "count": 0}` for memory, `{"installed": false}` for openspec) and continues to the next project

### Requirement: Feature cache in table rendering
The `_create_project_header` method SHALL read feature status from `self._feature_cache[project]` instead of calling subprocesses. The `get_memory_status` method SHALL read from cache and NOT run subprocess calls. The `get_openspec_status` method SHALL be called to retrieve openspec status before accessing its fields.

#### Scenario: Table render uses cache
- **WHEN** `refresh_table_display` rebuilds the table
- **THEN** `_create_project_header` reads `self._feature_cache.get(project, {})` for both memory and openspec button states, with zero subprocess calls

#### Scenario: Cache not yet populated
- **WHEN** the table renders before the first FeatureWorker poll completes
- **THEN** all feature buttons show gray/default state (memory: gray "checking...", openspec: gray "checking...")

#### Scenario: OpenSpec status variable is defined before use
- **WHEN** `_create_project_header` renders the OpenSpec [O] button
- **THEN** `os_status` is obtained via `self.get_openspec_status(project)` before any access to `os_status.get()`
- **AND** no NameError occurs regardless of cache state

### Requirement: Manual cache refresh trigger
The GUI SHALL provide a method `refresh_feature_cache()` that forces the FeatureWorker to run an immediate poll cycle. This SHALL be called after OpenSpec init/update operations complete.

#### Scenario: After OpenSpec init
- **WHEN** the "Initialize OpenSpec..." action completes via CommandOutputDialog
- **THEN** the GUI calls `refresh_feature_cache()` and the [O] button updates to green within the next table render cycle

## Purpose
Extended typed state with mutation methods, file locking, dependency graph, and phase management.
## Requirements

## MODIFIED Requirements

### Requirement: Atomic state saving
`save_state(state, path)` SHALL serialize the `OrchestratorState` to JSON and write atomically (tempfile in same directory + rename). It SHALL acquire an `fcntl.flock` advisory lock before writing and release it after rename. It SHALL validate the output is non-empty before rename.

#### Scenario: Successful save with locking
- **WHEN** `save_state(state, "orchestration-state.json")` is called
- **THEN** the file is written atomically under flock — concurrent readers/writers are serialized
- **AND** the lock file is `orchestration-state.json.lock`

#### Scenario: Disk full or write error
- **WHEN** the tempfile write fails (disk full, permission denied)
- **THEN** the original file is not modified, the lock is released, and an exception is raised

#### Scenario: Lock timeout
- **WHEN** another process holds the lock for an extended period
- **THEN** `save_state` blocks until the lock is available (no timeout — flock semantics)

### Requirement: CLI bridge for state operations
The `wt-orch-core state` CLI SHALL expose subcommands for each migrated state function, accepting arguments via flags and outputting results to stdout (JSON or plain text as appropriate).

#### Scenario: Update change field via CLI
- **WHEN** `wt-orch-core state update-change --file state.json --name add-auth --field status --value '"running"'` is called
- **THEN** the change field is updated atomically and the process exits with code 0

#### Scenario: Query change status via CLI
- **WHEN** `wt-orch-core state get-status --file state.json --name add-auth` is called
- **THEN** the status string is printed to stdout

#### Scenario: Topological sort via CLI
- **WHEN** `wt-orch-core state topo-sort --plan-file plan.json` is called
- **THEN** change names are printed one per line in dependency order

#### Scenario: Cascade failed via CLI
- **WHEN** `wt-orch-core state cascade-failed --file state.json` is called
- **THEN** pending changes with failed deps are marked failed and the count is printed

## MODIFIED Requirements

### Requirement: Configuration via environment variables
The CLI SHALL read configuration from environment variables: `SHODH_STORAGE` (default `~/.local/share/set-core/memory`). The storage path is the root under which per-project directories are created. The previous `SHODH_HOST`, `SHODH_PORT`, and `SHODH_API_KEY` variables are no longer used (shodh-memory is a local Python library, not a REST service).

#### Scenario: Default storage root
- **WHEN** `set-memory` is run without `SHODH_STORAGE` set
- **THEN** per-project storage directories are created under `~/.local/share/set-core/memory/`

#### Scenario: Custom storage root
- **WHEN** `SHODH_STORAGE=/custom/path set-memory recall "query"` is run from a git repo named "myproject"
- **THEN** storage path is `/custom/path/myproject/`

### Requirement: Health check command
The `set-memory health` command SHALL check if the shodh-memory Python package is importable. It SHALL return exit code 0 and print "ok" on success, or exit code 1 on failure. No network check is needed (library, not service).

#### Scenario: Shodh-memory installed
- **WHEN** `python3 -c "from shodh_memory import Memory"` succeeds
- **THEN** `set-memory health` returns exit code 0 and prints "ok"

#### Scenario: Shodh-memory not installed
- **WHEN** the shodh-memory Python package is not installed
- **THEN** `set-memory health` returns exit code 1

### Requirement: Remember command uses per-project storage
The `set-memory remember` command SHALL resolve the project from git root (or `--project` flag) and instantiate `Memory(storage_path=<project-dir>)` before saving.

#### Scenario: Remember in a git project
- **WHEN** `echo "pattern" | set-memory remember --type Learning` is run from a set-core worktree
- **THEN** the memory is stored under `~/.local/share/set-core/memory/set-core/`

### Requirement: Recall command uses per-project storage
The `set-memory recall` command SHALL resolve the project from git root (or `--project` flag) and instantiate `Memory(storage_path=<project-dir>)` before searching.

#### Scenario: Recall in a git project
- **WHEN** `set-memory recall "QTimer" --limit 3` is run from a set-core worktree
- **THEN** only memories from the set-core project storage are searched

### Requirement: Status command shows per-project info
The `set-memory status` command SHALL display the resolved project name, storage path, and memory count for the current project. When called with `--json`, it SHALL output a JSON object with fields: `available` (bool), `project` (string), `count` (int), `storage_path` (string).

#### Scenario: Status in a git project (human-readable)
- **WHEN** `set-memory status` is run from a set-core worktree
- **THEN** output shows project name "set-core", storage path, and memory count

#### Scenario: Status with --json flag
- **WHEN** `set-memory status --json --project set-core` is run
- **THEN** output is `{"available": true, "project": "set-core", "count": 2, "storage_path": "..."}`

#### Scenario: Status --json when shodh-memory not installed
- **WHEN** `set-memory status --json` is run and shodh-memory is not installed
- **THEN** output is `{"available": false, "project": "...", "count": 0, "storage_path": "..."}`

### Requirement: List memories command
The `set-memory list` command SHALL list all memories for the current project as JSON to stdout. It SHALL use `Memory.list_memories()` from the shodh-memory API. If shodh-memory is not installed, it SHALL output `[]` and exit 0.

#### Scenario: List memories for a project
- **WHEN** `set-memory list --project set-core` is run and the project has memories
- **THEN** output is a JSON array of memory objects with content, type, tags, created_at, id

#### Scenario: List when shodh-memory not installed
- **WHEN** `set-memory list` is run and shodh-memory is not installed
- **THEN** output is `[]` and exit code is 0

#### Scenario: List empty project
- **WHEN** `set-memory list --project new-project` is run and the project has no memories
- **THEN** output is `[]` and exit code is 0

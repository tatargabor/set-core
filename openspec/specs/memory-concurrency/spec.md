## Requirements

### Requirement: Daemon-first routing avoids lock contention
When the set-memoryd daemon is running, hook and MCP memory operations SHALL route through the daemon client instead of the `set-memory` CLI. CLI fallback SHALL only be attempted when the daemon is NOT running, preventing RocksDB lock conflicts between daemon and CLI processes.

#### Scenario: Daemon running, hook fires
- **WHEN** the set-memoryd daemon holds the RocksDB lock
- **AND** a hook or MCP tool needs to recall or remember
- **THEN** the operation SHALL use the daemon client (socket IPC)
- **AND** SHALL NOT spawn a `set-memory` CLI subprocess

#### Scenario: Daemon running, client fails
- **WHEN** the daemon client raises an exception
- **AND** the daemon process is still running (socket exists)
- **THEN** the operation SHALL NOT fall back to CLI (would cause lock conflict)
- **AND** SHALL return empty/failure gracefully

#### Scenario: Daemon not running, CLI fallback
- **WHEN** the daemon is not running (no socket file)
- **AND** the daemon client is unavailable
- **THEN** the operation SHALL fall back to the `set-memory` CLI with lock-based serialization

### Requirement: Serialized RocksDB Access
When the daemon is NOT running, all `set-memory` CLI operations that open the RocksDB storage SHALL be serialized through a per-project directory lock, preventing concurrent access failures.

#### Scenario: Concurrent remember and status calls
- **WHEN** the GUI FeatureWorker polls `set-memory status --json` while an agent session calls `set-memory remember`
- **THEN** the second call waits for the first to release the lock before proceeding
- **AND** both calls complete successfully

#### Scenario: Lock file per project
- **WHEN** `set-memory` is invoked for project "set-core"
- **THEN** it acquires a file lock at `/tmp/set-memory-set-core.lock`
- **AND** operations on different projects do NOT contend with each other

#### Scenario: Lock timeout
- **WHEN** a lock cannot be acquired within 10 seconds
- **THEN** the command SHALL check for stale locks (dead PID or age > 60s) before failing
- **AND** if a stale lock is found, remove it and retry acquisition once
- **AND** if retry also fails, the command SHALL fail with a non-zero exit code
- **AND** an error message SHALL be logged

### Requirement: Visible Error Reporting
The `set-memory` script SHALL log Python errors to a file instead of discarding them, so failures can be diagnosed.

#### Scenario: Python exception during remember
- **WHEN** the shodh-memory `remember()` call raises an exception
- **THEN** the error SHALL be appended to `<storage_path>/set-memory.log`
- **AND** the command SHALL return a non-zero exit code (unless graceful degradation applies)

#### Scenario: Shodh-memory not installed (graceful degradation)
- **WHEN** shodh-memory is not installed
- **THEN** `remember` SHALL exit 0 silently (no-op)
- **AND** `recall` and `list` SHALL return empty JSON arrays
- **AND** no error SHALL be logged

### Requirement: Banner Suppression Without Grep
The shodh-memory import banner SHALL be suppressed at the Python level, not via shell pipe filtering.

#### Scenario: No banner on stdout
- **WHEN** any `set-memory` command runs
- **THEN** the `⭐ Love shodh-memory?` banner SHALL NOT appear on stdout or stderr

#### Scenario: Python exit code preserved
- **WHEN** a `set-memory` command invokes Python internally
- **THEN** the Python process exit code SHALL propagate to the calling shell
- **AND** the exit code SHALL NOT be masked by pipe components

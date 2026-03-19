## ADDED Requirements

### Requirement: Stale lock detection and auto-recovery
The `run_with_lock()` function SHALL detect orphaned lock directories and automatically remove them before retrying acquisition.

#### Scenario: Lock orphaned by killed process
- **WHEN** a lock directory exists at `/tmp/set-memory-<project>.lock`
- **AND** the lock directory is older than 60 seconds
- **AND** no process holds a file descriptor on it
- **THEN** the function SHALL remove the stale lock directory
- **AND** proceed with normal lock acquisition

#### Scenario: Lock held by active process
- **WHEN** a lock directory exists at `/tmp/set-memory-<project>.lock`
- **AND** the lock directory is younger than 60 seconds
- **THEN** the function SHALL wait and retry as before (no forced removal)

#### Scenario: Stale lock removal logged
- **WHEN** a stale lock is detected and removed
- **THEN** a warning message SHALL be written to stderr: `set-memory: removed stale lock (age: Ns)`

### Requirement: Lock owner tracking
The lock directory SHALL contain a PID file to enable owner identification.

#### Scenario: PID written on lock acquisition
- **WHEN** `run_with_lock()` successfully acquires the lock
- **THEN** it SHALL write the current shell PID to `<lock_dir>/pid`

#### Scenario: PID-based staleness check
- **WHEN** a lock directory exists and contains a `pid` file
- **AND** the PID in the file is not a running process
- **THEN** the lock SHALL be considered stale regardless of age
- **AND** the function SHALL remove it and proceed

## MODIFIED Requirements

### Requirement: Lock timeout
The `run_with_lock()` function's timeout path SHALL include stale-lock recovery instead of silent failure.

#### Scenario: Lock timeout with stale detection
- **WHEN** a lock cannot be acquired within 10 seconds
- **THEN** the function SHALL check if the lock is stale (dead PID or age > 60s)
- **AND** if stale, remove it and retry once
- **AND** if not stale, fail with non-zero exit code and error message as before

## Requirements

### Requirement: Stale lock detection and auto-recovery
The `run_with_lock()` function SHALL detect orphaned lock directories and automatically remove them before retrying acquisition.

#### Scenario: Lock orphaned by killed process
- **WHEN** a lock directory exists at `/tmp/wt-memory-<project>.lock`
- **AND** the lock directory is older than 60 seconds
- **AND** no process holds a file descriptor on it
- **THEN** the function SHALL remove the stale lock directory
- **AND** proceed with normal lock acquisition

#### Scenario: Lock held by active process
- **WHEN** a lock directory exists at `/tmp/wt-memory-<project>.lock`
- **AND** the lock directory is younger than 60 seconds
- **THEN** the function SHALL wait and retry as before (no forced removal)

#### Scenario: Stale lock removal logged
- **WHEN** a stale lock is detected and removed
- **THEN** a warning message SHALL be written to stderr: `wt-memory: removed stale lock (age: Ns)`

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

---

## MODIFIED Requirements

### Requirement: Sentinel flock guard SHALL validate PID liveness before rejecting restart
When `flock -n` fails to acquire the sentinel lock, the sentinel SHALL check whether the process holding the lock is still alive. If the process is dead, the sentinel SHALL release the stale lock and retry acquisition.

#### Scenario: Previous sentinel died, flock still held
- **WHEN** `flock -n 9` fails (lock already held)
- **AND** the PID in `sentinel.pid` does not correspond to a running process (`kill -0 $pid` fails)
- **THEN** the sentinel SHALL remove `sentinel.lock`
- **AND** the sentinel SHALL re-open and re-acquire the flock
- **AND** the sentinel SHALL log "Recovered stale lock from dead PID $pid"

#### Scenario: Previous sentinel still running
- **WHEN** `flock -n 9` fails
- **AND** the PID in `sentinel.pid` is still alive (`kill -0 $pid` succeeds)
- **THEN** the sentinel SHALL exit with the existing error message "Another sentinel is already running"

#### Scenario: No PID file exists
- **WHEN** `flock -n 9` fails
- **AND** `sentinel.pid` does not exist or is empty
- **THEN** the sentinel SHALL remove `sentinel.lock` and retry flock acquisition
- **AND** the sentinel SHALL log "Recovered stale lock (no PID file)"

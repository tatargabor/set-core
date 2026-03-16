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

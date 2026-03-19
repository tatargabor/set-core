## ADDED Requirements

### Requirement: PID verification with process identity check
The system SHALL verify process identity (command line pattern) when checking PID liveness, not just whether the PID exists. `check_pid(pid, expected_cmdline_pattern)` SHALL return true only if the process exists AND its cmdline matches the expected pattern.

#### Scenario: Valid PID with matching command
- **WHEN** `check_pid(pid=1234, expected_cmdline_pattern="wt-loop")` is called and PID 1234 is alive running `wt-loop start ...`
- **THEN** the function returns `True`

#### Scenario: Recycled PID with different command
- **WHEN** `check_pid(pid=1234, expected_cmdline_pattern="wt-loop")` is called and PID 1234 is alive but running `/usr/bin/python3 other-script`
- **THEN** the function returns `False`

#### Scenario: Dead PID
- **WHEN** `check_pid(pid=9999, expected_cmdline_pattern="wt-loop")` is called and PID 9999 does not exist
- **THEN** the function returns `False`

#### Scenario: Permission denied reading process info
- **WHEN** `check_pid` is called for a PID owned by another user and `/proc/<pid>/cmdline` is not readable
- **THEN** the function falls back to `kill -0` semantics (returns `True` if PID exists) and logs a warning

### Requirement: Safe process termination sequence
The system SHALL implement a safe kill sequence that verifies process identity before and after each signal. `safe_kill(pid, expected_cmdline_pattern, timeout=10)` SHALL send SIGTERM, wait up to `timeout` seconds, then SIGKILL only if the process is still alive and still matches the expected pattern.

#### Scenario: Process exits after SIGTERM
- **WHEN** `safe_kill(pid=1234, expected_cmdline_pattern="wt-loop", timeout=10)` is called and the process exits within 3 seconds of SIGTERM
- **THEN** the function returns a result indicating `terminated` and does not send SIGKILL

#### Scenario: Process ignores SIGTERM
- **WHEN** `safe_kill` is called and the process does not exit within `timeout` seconds after SIGTERM
- **THEN** the function sends SIGKILL and returns a result indicating `killed`

#### Scenario: PID recycled between SIGTERM and SIGKILL
- **WHEN** SIGTERM causes the process to exit, and the OS reassigns the PID to a new process before SIGKILL would be sent
- **THEN** the function detects the cmdline mismatch and does NOT send SIGKILL, returning `terminated`

#### Scenario: Process already dead
- **WHEN** `safe_kill` is called for a PID that is already dead
- **THEN** the function returns a result indicating `already_dead` without sending any signal

### Requirement: Orphan process detection
The system SHALL detect orphaned orchestration processes (wt-loop instances with no corresponding active change in state). `find_orphans(expected_pattern, known_pids)` SHALL scan running processes matching the pattern and return those whose PIDs are not in the known set.

#### Scenario: Orphaned wt-loop found
- **WHEN** `find_orphans(expected_pattern="wt-loop", known_pids=[1234, 5678])` is called and PID 9999 is running `wt-loop start ... --change my-change`
- **THEN** the function returns an OrphanInfo with pid=9999, cmdline containing "wt-loop", and the extracted change name

#### Scenario: All processes accounted for
- **WHEN** all running wt-loop processes have PIDs in the `known_pids` set
- **THEN** the function returns an empty list

#### Scenario: psutil unavailable
- **WHEN** psutil cannot be imported
- **THEN** the function falls back to scanning `/proc/*/cmdline` on Linux, or returns an empty list with a warning on other platforms

### Requirement: CLI bridge for process operations
The `set-orch-core process` subcommand SHALL expose process operations to bash scripts via exit codes and stdout JSON.

#### Scenario: check-pid returns JSON result
- **WHEN** bash calls `set-orch-core process check-pid --pid 1234 --expect-cmd "wt-loop"`
- **THEN** stdout contains `{"alive": true, "match": true}` or `{"alive": false, "match": false}` and exit code is 0 for alive+match, 1 otherwise

#### Scenario: safe-kill returns JSON result
- **WHEN** bash calls `set-orch-core process safe-kill --pid 1234 --expect-cmd "wt-loop" --timeout 10`
- **THEN** stdout contains `{"result": "terminated", "signal": "SIGTERM"}` and exit code is 0

#### Scenario: find-orphans returns JSON list
- **WHEN** bash calls `set-orch-core process find-orphans --expect-cmd "wt-loop" --known-pids "1234,5678"`
- **THEN** stdout contains a JSON array of orphan objects

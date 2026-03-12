## MODIFIED Requirements

### Requirement: Watchdog uses identity-verified PID checks
The watchdog SHALL use `wt-orch-core process check-pid` with cmdline pattern verification for all process liveness decisions, replacing raw `kill -0` calls. This prevents false-positive "PID alive" results from recycled PIDs.

#### Scenario: Hash loop detection with PID identity check
- **WHEN** the watchdog detects consecutive identical action hashes and checks if the Ralph PID is alive
- **THEN** it calls `wt-orch-core process check-pid --pid $ralph_pid --expect-cmd "wt-loop"` instead of `kill -0 $ralph_pid`

#### Scenario: Timeout detection with PID identity check
- **WHEN** the watchdog detects no activity for the timeout threshold and checks PID liveness
- **THEN** it calls `wt-orch-core process check-pid --pid $ralph_pid --expect-cmd "wt-loop"` to distinguish a long-running iteration from a dead/recycled process

#### Scenario: Recycled PID detected as dead
- **WHEN** the original wt-loop process died and the OS assigned the same PID to an unrelated process
- **THEN** `check-pid` returns false (cmdline mismatch) and the watchdog escalates correctly instead of skipping escalation

### Requirement: Watchdog escalation uses safe-kill
The watchdog escalation chain SHALL use `wt-orch-core process safe-kill` for process termination at escalation levels 3+ (redispatch/fail), replacing manual signal sequences.

#### Scenario: Escalation level 3 — redispatch with safe kill
- **WHEN** the watchdog escalates to level 3 and calls `redispatch_change()`
- **THEN** the redispatch function uses `wt-orch-core process safe-kill` which verifies identity before SIGTERM and before SIGKILL

## ADDED Requirements

### Requirement: Python watchdog check pipeline
The system SHALL provide `watchdog_check()` in `lib/set_orch/watchdog.py` that replicates the full bash watchdog pipeline: state init, activity detection, action hash computation, stuck/spinning detection, and escalation.

#### Scenario: Healthy change with activity
- **WHEN** watchdog checks a change that has recent activity (loop-state.json mtime updated)
- **THEN** the watchdog resets its timeout counter and reports healthy status

#### Scenario: Stuck change detection
- **WHEN** the action hash has not changed for the configured timeout period
- **THEN** the watchdog escalates according to the escalation chain

#### Scenario: Spinning change detection
- **WHEN** 3+ iterations occur without any git commits
- **THEN** the watchdog detects spinning and escalates

### Requirement: Python action hash ring
The system SHALL implement an action hash ring buffer in `watchdog.py` using `hashlib.md5()` on (loop_state_mtime, tokens_used, ralph_status) to detect stuck loops.

#### Scenario: Hash ring duplicate detection
- **WHEN** the same action hash appears consecutively in the ring buffer
- **THEN** the change is flagged as potentially stuck

#### Scenario: Grace period for new changes
- **WHEN** loop-state.json does not exist yet (change just started)
- **THEN** hash detection is skipped during the grace period

### Requirement: Python escalation chain
The system SHALL implement escalation levels L1-L4 in `watchdog.py`: L1=warn, L2=resume, L3=redispatch, L4=fail. Each level triggers appropriate action.

#### Scenario: L1 warn escalation
- **WHEN** a change first becomes stuck
- **THEN** a warning event is emitted but no corrective action is taken

#### Scenario: L3 redispatch escalation
- **WHEN** a change remains stuck after L2 resume attempt
- **THEN** the change is redispatched to a new worktree

#### Scenario: L4 fail with partial salvage
- **WHEN** a change remains stuck after L3 redispatch
- **THEN** the change is marked failed and partial work is salvaged via diff capture

### Requirement: Python watchdog heartbeat
The system SHALL emit WATCHDOG_HEARTBEAT events via `events.emit()` for sentinel monitoring.

#### Scenario: Heartbeat emission
- **WHEN** watchdog completes a check cycle
- **THEN** a WATCHDOG_HEARTBEAT event is emitted with change name and status

### Requirement: Bash watchdog.sh becomes thin wrapper
After migration, `watchdog.sh` SHALL contain only delegation to `set-orch-core watchdog check`.

#### Scenario: Thin wrapper delegation
- **WHEN** `watchdog_check()` is called in bash
- **THEN** it delegates to `set-orch-core watchdog check` with equivalent arguments

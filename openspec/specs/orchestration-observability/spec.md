# Orchestration Observability

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Python stdlib `logging` instrumentation for all core orchestration modules
- Structured log messages with contextual fields (change name, gate name, PID, state field)
- INFO level for operational events (state transitions, gate outcomes, process lifecycle)
- DEBUG level for detailed internals (hash values, search paths, binding decisions)
- WARNING level for anomalies (missing files, fallback paths, unexpected state)
- Bash script logging via set-common.sh shared functions

### Out of scope
- Log aggregation or external log shipping (ELK, Datadog, etc.)
- Log rotation configuration changes
- Structured JSON logging format (plain text is sufficient)
- New logging dependencies (no structlog, loguru, etc.)
- Web dashboard log viewer changes
- Performance metrics or tracing (spans, timers)

## Requirements

### Requirement: State mutation logging
The system SHALL log every state file mutation with the field name, old value, new value, and change context.

#### Scenario: Change status transition
- **WHEN** a change status is updated (e.g., dispatched → implementing → merging)
- **THEN** state.py logs at INFO: `"State update: {change}.{field} = {new_value} (was: {old_value})"`

#### Scenario: Lock acquisition and release
- **WHEN** a state lock is acquired or released
- **THEN** state.py logs at DEBUG: `"State lock {acquired|released} by {caller}"`

#### Scenario: Crash recovery
- **WHEN** crash recovery detects and fixes stale state
- **THEN** state.py logs at WARNING: `"Crash recovery: reset {change} from {old_status} to {new_status}"`

### Requirement: Sentinel operation logging
The system SHALL log all sentinel finding, status, and event operations.

#### Scenario: Finding created
- **WHEN** a sentinel finding is recorded
- **THEN** sentinel/findings.py logs at INFO: `"Finding recorded: {severity} — {summary}"`

#### Scenario: Sentinel heartbeat
- **WHEN** a sentinel status heartbeat is emitted
- **THEN** sentinel/status.py logs at DEBUG: `"Sentinel heartbeat: session={session_id}, uptime={seconds}s"`

#### Scenario: Sentinel event emitted
- **WHEN** a sentinel event is emitted (poll, crash detect, inbox)
- **THEN** sentinel/events.py logs at INFO: `"Sentinel event: {event_type} — {detail}"`

### Requirement: Loop task logging
The system SHALL log task file discovery, parsing, and completion checks.

#### Scenario: Task file search
- **WHEN** find_tasks_file() searches for a tasks.md file
- **THEN** loop_tasks.py logs at DEBUG each directory searched and at INFO the file found or WARNING if none found

#### Scenario: Task completion check
- **WHEN** check_completion() evaluates task progress
- **THEN** loop_tasks.py logs at INFO: `"Task progress: {completed}/{total} tasks complete"`

### Requirement: Process lifecycle logging
The system SHALL log process creation, termination, and zombie detection.

#### Scenario: PID check
- **WHEN** check_pid() verifies a process is alive
- **THEN** process.py logs at DEBUG: `"PID {pid} status: {alive|dead}"`

#### Scenario: Process kill
- **WHEN** safe_kill() terminates a process
- **THEN** process.py logs at INFO: `"Killing PID {pid} (signal={signal})"`

#### Scenario: Zombie detection
- **WHEN** zombie reaping detects a defunct process
- **THEN** process.py logs at WARNING: `"Zombie process detected: PID {pid}"`

### Requirement: Gate execution logging
The system SHALL log gate ordering, retry context, and skip/warn/block decisions.

#### Scenario: Gate order resolved
- **WHEN** gate_runner resolves execution order
- **THEN** gate_runner.py logs at INFO the ordered list of gates to execute

#### Scenario: Gate skip or warn
- **WHEN** a gate is skipped or produces a warning instead of blocking
- **THEN** gate_runner.py logs at INFO: `"Gate {name}: {skip|warn|block} — {reason}"`

#### Scenario: Retry context injected
- **WHEN** retry context is built for a failed gate
- **THEN** gate_runner.py logs at DEBUG the context summary being injected

### Requirement: Test coverage binding logging
The system SHALL log the test-to-requirement binding algorithm decisions.

#### Scenario: Deterministic binding
- **WHEN** a test is bound to a requirement by exact REQ-ID match
- **THEN** test_coverage.py logs at DEBUG: `"Bound test '{test}' to {req_id} (exact match)"`

#### Scenario: Fuzzy binding
- **WHEN** a test is bound by fuzzy name matching
- **THEN** test_coverage.py logs at DEBUG: `"Bound test '{test}' to {req_id} (fuzzy, score={score})"`

#### Scenario: Unbound test
- **WHEN** a test cannot be bound to any requirement
- **THEN** test_coverage.py logs at WARNING: `"Unbound test: '{test}' — no matching requirement found"`

### Requirement: Profile system logging
The system SHALL log profile type resolution and rule/directive evaluation.

#### Scenario: Profile method invoked
- **WHEN** a ProjectType method is called (detect_test_command, get_forbidden_patterns, etc.)
- **THEN** profile_types.py logs at DEBUG: `"Profile.{method}() called, result: {summary}"`

### Requirement: Watchdog detail logging
The system SHALL log escalation level changes and progress tracking.

#### Scenario: Escalation level change
- **WHEN** watchdog changes escalation level for a change
- **THEN** watchdog.py logs at INFO: `"Watchdog escalation: {change} level {old} → {new}"`

#### Scenario: Progress hash update
- **WHEN** watchdog updates a progress hash
- **THEN** watchdog.py logs at DEBUG: `"Watchdog hash update: {change} = {hash}"`

### Requirement: Loop state logging
The system SHALL log state persistence and token accumulation.

#### Scenario: State file written
- **WHEN** loop state is persisted to disk
- **THEN** loop_state.py logs at DEBUG: `"Loop state saved: iteration={n}, tokens={total}"`

#### Scenario: Token accumulation
- **WHEN** tokens are accumulated for a loop iteration
- **THEN** loop_state.py logs at DEBUG: `"Token accumulation: +{delta} = {total}"`

### Requirement: Bash script logging
Silent bash scripts in bin/ SHALL use set-common.sh logging functions for status output.

#### Scenario: Script start and exit
- **WHEN** a bash script starts or exits
- **THEN** it logs at INFO: `"[script-name] started"` / `"[script-name] completed (exit={code})"`

#### Scenario: Key operation
- **WHEN** a bash script performs a key operation (file copy, git operation, API call)
- **THEN** it logs at INFO describing the operation

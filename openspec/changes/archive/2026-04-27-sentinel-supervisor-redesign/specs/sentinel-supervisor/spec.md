## ADDED Requirements

### Requirement: Supervisor is a Python daemon, not a Claude conversation
The orchestration supervisor SHALL be implemented as a long-running Python process (`set-supervisor`) rather than a `claude -p` conversation. Routine polling, process monitoring, and state inspection SHALL NOT consume LLM tokens. The daemon SHALL survive arbitrary-length runs without context exhaustion.

#### Scenario: Supervisor runs for 4 hours without token accumulation
- **GIVEN** a spec that takes 4 hours to decompose and execute
- **WHEN** `set-supervisor` is started via the manager API
- **THEN** the supervisor process is still alive at the end of the run
- **AND** its routine poll cycle (every 15s) has consumed zero LLM tokens
- **AND** all LLM invocations have been ephemeral (trigger or canary), each < 5 minutes

#### Scenario: Supervisor survives orchestrator crash restart cycle
- **GIVEN** the orchestrator crashes with SIGKILL
- **WHEN** the supervisor detects the crash
- **THEN** the supervisor restarts the orchestrator within 30 seconds
- **AND** the supervisor process itself does NOT exit

### Requirement: Supervisor triggers ephemeral Claude only on anomaly signals
The supervisor SHALL maintain a fixed set of anomaly signals and SHALL invoke a fresh ephemeral Claude subprocess only when one of these signals fires. Routine polling SHALL NOT invoke Claude.

#### Scenario: Idle run fires zero triggers
- **GIVEN** an orchestration run where every change merges cleanly on first attempt
- **AND** no crashes, no stalls, no integration failures
- **WHEN** the supervisor watches the run from start to finish
- **THEN** zero Layer 2 trigger invocations happen
- **AND** only the periodic canary checks consume LLM tokens

#### Scenario: Integration-failed triggers ephemeral Claude for diagnosis
- **GIVEN** a change enters `integration-failed` status
- **WHEN** the supervisor detects the status transition
- **THEN** a fresh `claude -p` subprocess is spawned with the `integration_failed` trigger prompt
- **AND** the subprocess receives the change name, the integration gate output, and the list of allowed recovery actions
- **AND** the subprocess exits within 10 minutes
- **AND** the subprocess's decisions are emitted as events in `orchestration-events.jsonl`

#### Scenario: Unknown event type fires one trigger on first occurrence
- **GIVEN** a new event type appears in `events.jsonl` that the supervisor's known-types set does not include
- **WHEN** the supervisor processes the event stream
- **THEN** exactly one Layer 2 trigger is fired for that event type
- **AND** the new event type is added to the known-types set for the remainder of the run
- **AND** subsequent occurrences of the same event type do NOT re-fire the trigger

### Requirement: Canary Claude provides periodic open-ended oversight
The supervisor SHALL spawn a periodic canary Claude subprocess every 15 minutes (configurable) regardless of trigger activity. The canary SHALL receive a structured diff of activity since the previous canary and decide whether the run warrants escalation.

#### Scenario: Canary sees a clean run and returns OK
- **GIVEN** the supervisor has been monitoring for 15 minutes with no anomalies
- **WHEN** the canary spawn time arrives
- **THEN** a fresh ephemeral Claude is spawned with the 15-minute diff as context
- **AND** the Claude returns `CANARY_VERDICT: ok`
- **AND** the supervisor records the verdict and continues monitoring

#### Scenario: Canary sees a slow-burn issue and escalates
- **GIVEN** the supervisor has seen a gradual increase in warn-level log lines over 45 minutes
- **AND** no individual trigger has fired
- **WHEN** the next canary check runs
- **THEN** the canary may return `CANARY_VERDICT: warn` with a suggested action
- **AND** the supervisor records the warning
- **AND** rate-limits repeat warnings about the same pattern to at most once per 30 minutes

#### Scenario: Missing CANARY_VERDICT sentinel defaults to note
- **GIVEN** the canary Claude emits a narrative response without the `CANARY_VERDICT:` sentinel line
- **WHEN** the supervisor parses the response
- **THEN** the verdict is treated as `note` (lowest severity)
- **AND** the supervisor logs the missing-sentinel anomaly
- **AND** the run continues without escalation

### Requirement: Supervisor emits observability events to the dashboard
The supervisor SHALL emit structured events to `orchestration-events.jsonl` so the set-web dashboard can render supervision history without a new event reader.

#### Scenario: Start and stop events
- **WHEN** the supervisor starts
- **THEN** a `SUPERVISOR_START` event is emitted with the orchestrator PID and daemon PID
- **WHEN** the supervisor stops
- **THEN** a `SUPERVISOR_STOP` event is emitted with the exit reason and total poll cycles

#### Scenario: Trigger and canary events
- **WHEN** a Layer 2 trigger fires
- **THEN** a `SUPERVISOR_TRIGGER` event is emitted with the trigger name, the spawned Claude PID, and the exit code on completion
- **WHEN** a Layer 3 canary check runs
- **THEN** a `CANARY_CHECK` event is emitted with the verdict and elapsed time

### Requirement: Rollback directive allows reverting to Claude sentinel
The supervisor mode SHALL be controlled by a directive `supervisor_mode: "python" | "claude" | "off"` with default `"python"`. Operators SHALL be able to fall back to the legacy Claude sentinel without redeploying by setting the directive and restarting.

#### Scenario: Default is python
- **WHEN** a project starts with no explicit `supervisor_mode` directive
- **THEN** the manager API spawns `set-supervisor` (Python daemon)

#### Scenario: claude mode uses legacy sentinel
- **GIVEN** the directive `supervisor_mode: claude`
- **WHEN** the manager API starts supervision
- **THEN** it spawns the legacy `claude -p` sentinel via the old sentinel.md skill

#### Scenario: off mode runs with no supervision
- **GIVEN** the directive `supervisor_mode: off`
- **WHEN** the manager API starts supervision
- **THEN** it starts `set-orchestrate` directly with no supervisor wrapper
- **AND** crash recovery and canary checks are disabled

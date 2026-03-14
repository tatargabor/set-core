## Purpose
Event bus with JSONL persistence for orchestration audit trail and in-process pub/sub.

## Requirements

### Requirement: Event emission
The system SHALL provide an `emit()` function that writes structured events to a JSONL file. Migrated from: `events.sh:emit_event()` L19-61.

#### Scenario: Emit event with change
- **WHEN** `emit("STATE_CHANGE", change="add-auth", data={"status": "running"})` is called
- **THEN** a JSON line is appended to the events JSONL file: `{"ts":"<ISO8601>","type":"STATE_CHANGE","change":"add-auth","data":{"status":"running"}}`

#### Scenario: Emit event without change
- **WHEN** `emit("CHECKPOINT", data={"reason": "user"})` is called
- **THEN** a JSON line is appended without the `change` field: `{"ts":"<ISO8601>","type":"CHECKPOINT","data":{"reason":"user"}}`

#### Scenario: Events disabled
- **WHEN** events are disabled via configuration
- **THEN** `emit()` returns immediately without writing

#### Scenario: Lazy log path initialization
- **WHEN** the events log file path is not set and `STATE_FILENAME` env var exists
- **THEN** the log path is derived as `<state_file_stem>-events.jsonl`

### Requirement: JSONL format compatibility
The JSONL output format SHALL be byte-compatible with the existing `events.sh` output.

#### Scenario: Format verification
- **WHEN** an event is emitted
- **THEN** the JSON line contains exactly these fields in order: `ts`, `type`, optionally `change`, `data`
- **AND** `ts` uses ISO 8601 format with timezone (matching `date -Iseconds`)
- **AND** `data` is always a valid JSON object (default `{}`)

### Requirement: Event log rotation
The system SHALL provide a `rotate_log()` function. Migrated from: `events.sh:rotate_events_log()` L66-86.

#### Scenario: Rotation trigger
- **WHEN** the events log file exceeds `max_size` bytes (default 1MB)
- **THEN** the file is renamed with a timestamp suffix (`-YYYYMMDDHHMMSS.jsonl`)
- **AND** a new empty log file is created
- **AND** only the last 3 archives are kept

#### Scenario: Periodic rotation check
- **WHEN** every 100th event is emitted
- **THEN** rotation is automatically checked

### Requirement: Event querying
The system SHALL provide a `query_events()` function. Migrated from: `events.sh:query_events()` L92-139.

#### Scenario: Query by type
- **WHEN** `query_events(type="STATE_CHANGE")` is called
- **THEN** only events with matching type are returned

#### Scenario: Query by change name
- **WHEN** `query_events(change="add-auth")` is called
- **THEN** only events for that change are returned

#### Scenario: Query with last N
- **WHEN** `query_events(last_n=50)` is called
- **THEN** only the last 50 lines of the log are scanned

#### Scenario: Combined filters
- **WHEN** `query_events(type="STATE_CHANGE", change="add-auth", since="2026-03-14T00:00:00")` is called
- **THEN** all filters are applied with AND logic

### Requirement: Event bus with subscribe
The system SHALL provide an in-process event bus with `subscribe()` and `emit()` for internal Python consumers.

#### Scenario: Subscribe to events
- **WHEN** `bus.subscribe("STATE_CHANGE", handler_fn)` is called
- **AND** a STATE_CHANGE event is emitted
- **THEN** `handler_fn(event)` is called synchronously

#### Scenario: Multiple subscribers
- **WHEN** multiple handlers subscribe to the same event type
- **THEN** all handlers are called in registration order

#### Scenario: Wildcard subscription
- **WHEN** `bus.subscribe("*", handler_fn)` is called
- **THEN** the handler receives all events regardless of type

### Requirement: CLI integration
The events module SHALL be callable via `wt-orch-core events` subcommand.

#### Scenario: Query events via CLI
- **WHEN** `wt-orch-core events --type STATE_CHANGE --last 20 --json` is called
- **THEN** it outputs matching events as a JSON array to stdout

#### Scenario: Formatted output
- **WHEN** `wt-orch-core events --last 10` is called (without --json)
- **THEN** events are printed in a formatted table: Timestamp, Type, Change, Data

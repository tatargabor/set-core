# Sentinel Events Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Structured event logging to `.wt/sentinel/events.jsonl` (append-only JSONL)
- Event types: poll, crash, restart, decision, escalation, finding, assessment, message_received, message_sent
- Python API for emitting events (`lib/set_orch/sentinel/events.py`)
- CLI wrapper for bash sentinel compatibility
- Run rotation (archive old events on new run start)
- `.wt/` directory creation and `.gitignore` entry

### Out of scope
- set-web display of events (covered by sentinel-dashboard spec)
- Findings aggregation (covered by sentinel-findings spec)
- Inbox/outbox messaging (covered by sentinel-messaging spec)

## Requirements

### Requirement: Structured event logging
The system SHALL write sentinel events as newline-delimited JSON to `.wt/sentinel/events.jsonl`. Each event SHALL contain a `ts` field (ISO 8601 timestamp), a `type` field (string enum), and type-specific data fields.

#### Scenario: Poll event emitted
- **WHEN** the sentinel polls orchestration state
- **THEN** an event with `type: "poll"` is appended to `events.jsonl` containing `state`, `change` (current active change name if any), and `iteration` (current iteration number if applicable)

#### Scenario: Crash event emitted
- **WHEN** the sentinel detects an orchestrator process crash
- **THEN** an event with `type: "crash"` is appended containing `pid`, `exit_code`, and `stderr_tail` (last 500 chars of stderr)

#### Scenario: Restart event emitted
- **WHEN** the sentinel restarts the orchestrator
- **THEN** an event with `type: "restart"` is appended containing `new_pid` and `attempt` (restart attempt number)

#### Scenario: Decision event emitted
- **WHEN** the sentinel makes an autonomous decision (e.g., auto-approve checkpoint)
- **THEN** an event with `type: "decision"` is appended containing `action` and `reason`

#### Scenario: Escalation event emitted
- **WHEN** the sentinel needs user input (e.g., non-periodic checkpoint)
- **THEN** an event with `type: "escalation"` is appended containing `reason` and `context`

### Requirement: Event logging Python API
The system SHALL provide a Python module `lib/set_orch/sentinel/events.py` with a `SentinelEventLogger` class that provides typed methods for each event type.

#### Scenario: Logger initialization with project path
- **WHEN** `SentinelEventLogger(project_path)` is instantiated
- **THEN** it SHALL create `.wt/sentinel/` directory if it does not exist and open `events.jsonl` for appending

#### Scenario: Logger creates .wt directory and gitignore
- **WHEN** the logger initializes and `.wt/` does not exist
- **THEN** it SHALL create the directory AND append `/.set/` to the project's `.gitignore` if not already present

### Requirement: Event logging CLI
The system SHALL provide a CLI command `set-sentinel-log` that wraps the Python API for use from bash scripts.

#### Scenario: CLI poll event
- **WHEN** `set-sentinel-log poll --state running --change add-products --iteration 42` is executed
- **THEN** a poll event is appended to `events.jsonl` with the provided fields

#### Scenario: CLI crash event
- **WHEN** `set-sentinel-log crash --pid 45231 --exit-code 1 --stderr "error text"` is executed
- **THEN** a crash event is appended to `events.jsonl`

### Requirement: Event rotation on new run
The system SHALL support rotating events.jsonl to an archive directory when a new orchestration run starts.

#### Scenario: Rotation moves old events to archive
- **WHEN** `SentinelEventLogger.rotate()` is called (or `set-sentinel-rotate`)
- **THEN** the current `events.jsonl` SHALL be moved to `.wt/sentinel/archive/events-{ISO-date}.jsonl` and a fresh empty `events.jsonl` SHALL be created

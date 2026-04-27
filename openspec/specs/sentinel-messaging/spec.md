# Sentinel Messaging Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Sentinel inbox polling at 3-5s intervals (lightweight file read)
- Splitting the sentinel main loop sleep for responsive inbox checks
- Message receipt logging as events
- Sentinel status/identity registration in `.wt/sentinel/status.json`
- Heartbeat updates to status.json

### Out of scope
- New messaging transport (uses existing set-control-chat / MCP send_message)
- set-web message sending UI (covered by sentinel-dashboard)
- Multi-sentinel coordination (single sentinel per project assumed)
- Encryption changes (existing NaCl box encryption unchanged)

## Requirements

### Requirement: Sentinel inbox polling
The sentinel main loop SHALL check for incoming messages every 3-5 seconds instead of only at state poll intervals.

#### Scenario: Bash sentinel inbox check
- **WHEN** the bash sentinel is in its 10s sleep between state polls
- **THEN** it SHALL split the sleep into 2x5s intervals and call `set-sentinel-inbox check` between them, achieving max 5s message latency

#### Scenario: Agent sentinel inbox check
- **WHEN** the agent sentinel is in its 30s sleep between state polls
- **THEN** it SHALL split the sleep into 10x3s intervals and check inbox between each, achieving max 3s message latency

#### Scenario: Message received during inbox check
- **WHEN** `set-sentinel-inbox check` finds a new message
- **THEN** the message content and sender SHALL be printed to stdout AND a `message_received` event SHALL be emitted to events.jsonl

### Requirement: Sentinel status registration
The sentinel SHALL register its identity in `.wt/sentinel/status.json` on startup and update it periodically.

#### Scenario: Sentinel startup registration
- **WHEN** the sentinel starts (bash or agent mode)
- **THEN** it SHALL write `status.json` containing `active: true`, `member` (team member name), `session_id` (if agent mode), `started_at` (ISO timestamp), `poll_interval_s`, and `orchestrator_pid`

#### Scenario: Heartbeat update
- **WHEN** the sentinel completes a state poll cycle
- **THEN** it SHALL update `last_event_at` in `status.json` to the current timestamp

#### Scenario: Sentinel shutdown
- **WHEN** the sentinel exits (clean or crash)
- **THEN** it SHALL set `active: false` in `status.json` (best-effort via signal handler)

### Requirement: Inbox Python API
The system SHALL provide `lib/set_orch/sentinel/inbox.py` with lightweight inbox check functions.

#### Scenario: Check inbox with no messages
- **WHEN** `check_inbox(member)` is called and no messages exist
- **THEN** it SHALL return an empty list in under 5ms (file read only, no git operations)

#### Scenario: Check inbox with messages
- **WHEN** `check_inbox(member)` is called and messages exist since last check
- **THEN** it SHALL return the new messages as a list of dicts with `from`, `content`, `timestamp`

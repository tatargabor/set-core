# Events API Specification

## Purpose

Define which event-stream file the `/api/{project}/events` HTTP endpoint and the state-reconstruction logic SHALL read, so the dashboard timeline tab and post-crash recovery both see the canonical run history.

## ADDED Requirements

### Requirement: events-api-prefers-live-stream

The `/api/{project}/events` endpoint SHALL resolve the events file by trying the following candidates in order and returning the FIRST that exists:

1. `<project_path>/orchestration-events.jsonl` — the live stream
2. `<project_path>/orchestration-state-events.jsonl` — the narrow stream (back-compat)
3. `<project_path>/set/orchestration/orchestration-events.jsonl` — legacy nested live
4. `<project_path>/set/orchestration/orchestration-state-events.jsonl` — legacy nested narrow

When none of the four files exist, the endpoint SHALL return `{"events": []}`.

The endpoint SHALL log the resolved file at DEBUG level so operators can trace the source.

The existing `type=<event_type>` query filter and `limit=<N>` parameter SHALL apply to whichever file resolves. `limit` selects the LAST N events in time order.

`reconstruct_state_from_events` in `lib/set_orch/state.py` SHALL apply the same resolution chain when `events_path` is None.

#### Scenario: live-stream-wins-over-narrow

- **GIVEN** a project directory containing both `orchestration-events.jsonl` (5,000 events) and `orchestration-state-events.jsonl` (5 events)
- **WHEN** `/api/{project}/events` is called with no filter and `limit=500`
- **THEN** the response contains 500 events drawn from `orchestration-events.jsonl`
- **AND** the response does NOT contain the 5 narrow-stream events

#### Scenario: narrow-stream-fallback

- **GIVEN** a project directory containing only `orchestration-state-events.jsonl`
- **WHEN** `/api/{project}/events` is called
- **THEN** the response contains events from the narrow stream

#### Scenario: legacy-nested-live-fallback

- **GIVEN** a project directory with no events files at the root, but `set/orchestration/orchestration-events.jsonl` exists
- **WHEN** `/api/{project}/events` is called
- **THEN** the response contains events from the legacy nested live file

#### Scenario: no-events-file-returns-empty

- **GIVEN** a project directory with none of the four event files
- **WHEN** `/api/{project}/events` is called
- **THEN** the response is `{"events": []}`

#### Scenario: limit-honored-on-resolved-file

- **GIVEN** the resolved events file contains 100 events
- **WHEN** `/api/{project}/events?limit=10` is called
- **THEN** the response contains the LAST 10 events in time order

#### Scenario: type-filter-applied-to-resolved-file

- **GIVEN** the resolved events file contains 5 `STATE_CHANGE` events mixed with 200 other events
- **WHEN** `/api/{project}/events?type=STATE_CHANGE&limit=500` is called
- **THEN** the response contains exactly those 5 `STATE_CHANGE` events

### Requirement: events-api-includes-rotated-cycles

When the resolved live event file's event count is less than the requested `limit`, the endpoint SHALL also read events from `paths.rotated_event_files` (the `orchestration-events-cycle*.jsonl` siblings) until either the limit is reached or no more cycles remain.

Rotated cycles SHALL be read in CHRONOLOGICAL order (oldest cycle first) and prepended to the live tail so the result is overall time-ordered.

The `type` filter SHALL apply equally to events from rotated cycles.

When the rotation enumeration raises an exception, the endpoint SHALL log a WARNING with `exc_info=True` and continue with the live tail only — never propagate the exception to the caller.

#### Scenario: rotation-fills-up-to-limit

- **GIVEN** the live file has 5 events
- **AND** one rotated cycle file has 30 events
- **WHEN** `/api/{project}/events?limit=20` is called
- **THEN** the response contains 20 events
- **AND** the first 15 are the most recent rotated-cycle events
- **AND** the last 5 are the live-file events
- **AND** the timestamps are monotonically non-decreasing

#### Scenario: live-tail-sufficient

- **GIVEN** the live file has 1,000 events
- **WHEN** `/api/{project}/events?limit=500` is called
- **THEN** no rotated cycle is read
- **AND** the response contains the last 500 events from the live file

#### Scenario: rotation-lookup-failure-non-fatal

- **GIVEN** the live file has 5 events
- **AND** the rotation enumerator raises an exception
- **WHEN** `/api/{project}/events?limit=20` is called
- **THEN** a WARNING is logged with `exc_info=True`
- **AND** the response contains the 5 live-file events
- **AND** no exception is propagated

### Requirement: state-reconstruct-uses-live-stream

When `lib/set_orch/state.py::reconstruct_state_from_events(state_path)` is called without an explicit `events_path` argument, it SHALL apply the same 4-step resolver chain as the API endpoint (live → narrow → legacy nested live → legacy nested narrow) and use the first existing file as the events source.

The function SHALL log the selected file at INFO level.

#### Scenario: reconstruct-prefers-live-stream

- **GIVEN** a project with both `orchestration-events.jsonl` (containing 12 `STATE_CHANGE` events for 12 changes) and `orchestration-state-events.jsonl` (containing only digest events)
- **WHEN** `reconstruct_state_from_events(state_path)` is called without `events_path`
- **THEN** the function reads from the live stream
- **AND** the reconstructed state has 12 changes with statuses derived from the live stream's `STATE_CHANGE` events (modulo the existing "running → stalled" rule for changes with no live process)

#### Scenario: reconstruct-replays-state-changes

- **GIVEN** the live stream contains, in order, `STATE_CHANGE` events with `data.to ∈ {running, done, merged}` for change `foo`
- **WHEN** reconstruction runs
- **THEN** the reconstructed `Change` for `foo` has `status="merged"` (the LAST `to` value)

#### Scenario: reconstruct-narrow-fallback

- **GIVEN** a project with only `orchestration-state-events.jsonl` present
- **WHEN** reconstruction runs without `events_path`
- **THEN** the narrow stream is used as the events source

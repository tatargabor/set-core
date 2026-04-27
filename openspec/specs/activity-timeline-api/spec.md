# Activity Timeline Api Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Span reconstruction from events

The system SHALL reconstruct typed activity spans by correlating events from multiple sources, including `LLM_CALL` events for Claude CLI work and a `DISPATCH`-based fallback for implementing spans when `STEP_TRANSITION` events are absent.

#### Scenario: LLM call span from LLM_CALL event (orchestrator source)

- **WHEN** the event log contains an `LLM_CALL` event from the orchestration source with `data.purpose="review"`, `data.duration_ms=120000`, and `ts=T` for change "add-auth"
- **THEN** a span SHALL be produced with `category="llm:review"`, `change="add-auth"`, `start=T - 120s`, `end=T`, `duration_ms=120000`
- **AND** the span's `detail` field SHALL include `model`, `cost_usd`, `input_tokens`, `output_tokens` from the event data

#### Scenario: LLM call span from sentinel source

- **WHEN** the event log contains an `LLM_CALL` event from `.set/sentinel/events.jsonl` (`_source="sentinel"`) with `data.purpose="poll"` and `data.duration_ms=5000`
- **THEN** a span SHALL be produced with `category="sentinel:llm:poll"` (not `llm:poll`)
- **AND** the span SHALL appear on its own sentinel lane in the UI

#### Scenario: LLM call with missing duration

- **WHEN** an `LLM_CALL` event has missing or zero `duration_ms`
- **THEN** a zero-length marker span SHALL be emitted at the event's `ts` (not dropped)
- **AND** a WARNING SHALL be logged with the event data

#### Scenario: Implementing span fallback from DISPATCH

- **WHEN** the event log contains a `DISPATCH` event for change "add-auth" at T1
- **AND** a subsequent `CHANGE_DONE` event for "add-auth" at T2
- **AND** no `STEP_TRANSITION` events exist for "add-auth"
- **THEN** an `implementing` span SHALL be produced with `change="add-auth"`, `start=T1`, `end=T2`

#### Scenario: DISPATCH fallback suppressed when STEP_TRANSITION present

- **WHEN** both a `DISPATCH` event and a `STEP_TRANSITION to=implementing` event exist for the same change
- **THEN** only the `STEP_TRANSITION`-derived implementing span SHALL be emitted
- **AND** the DISPATCH fallback span SHALL be suppressed

#### Scenario: Redispatch produces two implementing spans

- **WHEN** the event log contains `DISPATCH(change=X)` at T1, followed by `DISPATCH(change=X)` at T2, followed by `CHANGE_DONE(change=X)` at T3
- **THEN** two implementing spans SHALL be produced: one with `start=T1, end=T2` and one with `start=T2, end=T3`

#### Scenario: Implementing span closed by merge start

- **WHEN** the event log contains `DISPATCH(change=X)` at T1, followed by `MERGE_START(change=X)` at T2
- **THEN** the implementing span SHALL close at T2 (agent work is considered done once merge pipeline begins)

#### Scenario: Implementing span closed by failure transition

- **WHEN** the event log contains `DISPATCH(change=X)` at T1, followed by `STATE_CHANGE(change=X, to="failed")` at T2
- **THEN** the implementing span SHALL close at T2

#### Scenario: Gate span from GATE_START and GATE_PASS

- **WHEN** the event log contains `GATE_START` with `data.gate=build` for change "add-auth" at T1
- **AND** a subsequent `GATE_PASS` with `data.gate=build` for "add-auth" at T2
- **THEN** a span SHALL be produced with `category=gate:build`, `change=add-auth`, `start=T1`, `end=T2`, `duration_ms=T2-T1`

#### Scenario: Step-based span from STEP_TRANSITION

- **WHEN** the event log contains `STEP_TRANSITION` with `data.to=implementing` for change "add-auth" at T1
- **AND** a subsequent `STEP_TRANSITION` with `data.to=fixing` for "add-auth" at T2
- **THEN** a span SHALL be produced with `category=implementing`, `change=add-auth`, `start=T1`, `end=T2`

#### Scenario: Merge span from MERGE_START and MERGE_COMPLETE

- **WHEN** the event log contains `MERGE_START` for change "add-auth" at T1
- **AND** `MERGE_COMPLETE` for "add-auth" at T2
- **THEN** a span SHALL be produced with `category=merge`, `change=add-auth`, `start=T1`, `end=T2`

#### Scenario: Gate retry produces multiple spans

- **WHEN** a gate runs, fails, and retries
- **THEN** each attempt SHALL produce a separate span with a `retry` field indicating the attempt number
- **AND** the `result` field SHALL be `fail` for failed attempts and `pass` for the final successful attempt

### Requirement: Idle gap detection from span coverage

The system SHALL detect idle periods as time intervals not covered by any reconstructed activity span, using span-coverage analysis rather than raw event-pair gaps.

#### Scenario: Gap covered by implementing span is not idle

- **WHEN** an `implementing` span exists from T1 to T3
- **AND** no orchestration events (excluding heartbeats) exist between T1 and T3
- **THEN** no idle span SHALL be emitted for that interval

#### Scenario: Gap covered by LLM span is not idle

- **WHEN** an `llm:review` span exists from T1 to T2 with duration > 60s
- **AND** no other events exist in that window
- **THEN** no idle span SHALL be emitted for that interval

#### Scenario: Uncovered gap >60s becomes idle

- **WHEN** a time interval of 5 minutes exists with no span coverage of any kind
- **THEN** an `idle` span SHALL be emitted for that interval

#### Scenario: Uncovered gap ≤60s is not idle

- **WHEN** a time interval of 30 seconds exists with no span coverage
- **THEN** no idle span SHALL be emitted (below threshold)

#### Scenario: Partial overlap is treated as covered

- **WHEN** an implementing span runs from T1 to T2, and a gap between other events runs from T1+30s to T2+30s
- **THEN** only the uncovered portion (T2 to T2+30s) SHALL be checked against the idle threshold
- **AND** since the uncovered portion is 30s (< 60s), no idle span SHALL be emitted

### Requirement: Breakdown summary with parallel work semantics

The system SHALL compute a per-category breakdown from the reconstructed spans, correctly handling parallel work where total activity time may exceed wall time.

#### Scenario: Parallel LLM and implementing counted independently

- **WHEN** an `implementing` span runs from T1 to T3
- **AND** an `llm:review` span runs from T2 to T2+120s where T1 < T2 < T3
- **THEN** the breakdown for `implementing` and `llm:review` SHALL sum their independent durations
- **AND** `activity_time_ms` SHALL exceed the implementing duration alone
- **AND** `parallel_efficiency` SHALL be greater than 1.0 when significant parallel work exists

#### Scenario: Sentinel LLM counted as parallel activity

- **WHEN** a `sentinel:llm:poll` span exists concurrently with an `implementing` span
- **THEN** the sentinel span SHALL contribute to `activity_time_ms`
- **AND** both spans SHALL appear in the breakdown under their respective categories
## Requirements
### Requirement: Multi-cycle event file aggregation
The activity timeline API SHALL read every rotated `orchestration-events-cycle<N>.jsonl` and `orchestration-state-events-cycle<N>.jsonl` in the project root alongside the live files, so the returned spans cover the entire run history, not just the current cycle.

#### Scenario: Rotated cycles present
- **WHEN** the project root contains `orchestration-events-cycle1.jsonl`, `orchestration-events-cycle2.jsonl`, and the live `orchestration-events.jsonl`
- **THEN** the activity timeline reader SHALL load all three in ascending-cycle order
- **AND** the returned spans SHALL be ordered by their event timestamp, not by the file they came from

#### Scenario: Live-only project
- **WHEN** only the live `orchestration-events.jsonl` exists (no rotated files yet)
- **THEN** behaviour SHALL be identical to the pre-change reader (single-file read)

### Requirement: Sentinel-session boundary markers in the timeline
The activity timeline API SHALL emit a synthetic span of category `sentinel:session_boundary` at each `sentinel_started_at` timestamp, so the UI can render a visible separator between sessions.

#### Scenario: Two sentinel sessions in the run
- **WHEN** the rotated + live event files span two sessions with distinct `sentinel_session_id` values
- **THEN** a zero-width span with `category = "sentinel:session_boundary"`, `detail.session_id = <new session uuid>`, `detail.session_started_at = <iso>`, `detail.spec_lineage_id = <lineage>` SHALL be emitted at the boundary timestamp
- **AND** the span SHALL NOT inherit a change name or a change-specific lane

### Requirement: Lineage filtering on the activity timeline
The activity timeline endpoint SHALL honour the optional `?lineage=<id>` query parameter and return only spans whose originating events/records belong to that lineage.

#### Scenario: Filter to v1 while v2 runs live
- **WHEN** the client calls `GET /api/<project>/activity-timeline?lineage=docs/spec-v1.md`
- **AND** the live orchestration is running on v2
- **THEN** the response SHALL include only spans derived from events tagged with `spec_lineage_id = docs/spec-v1.md`
- **AND** no v2-lineage spans SHALL appear in the response

#### Scenario: Lineage parameter omitted
- **WHEN** the client calls the endpoint without a `lineage` parameter
- **THEN** the response SHALL be equivalent to `?lineage=<state.spec_lineage_id>` (live lineage is the default)

#### Scenario: All-lineages mode (backend-only compatibility shim)
- **WHEN** an external consumer calls the endpoint with `?lineage=__all__`
- **THEN** every span SHALL be returned regardless of lineage
- **AND** each span SHALL carry its `detail.spec_lineage_id` so the caller can regroup
- **AND** the dashboard UI SHALL NOT emit this request from any user-facing control


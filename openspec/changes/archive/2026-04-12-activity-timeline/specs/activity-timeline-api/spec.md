## ADDED Requirements

## IN SCOPE
- API endpoint that returns time-based activity spans from event sources
- Multi-source event merging (orchestration events, sentinel events, loop state)
- Per-category breakdown with total time and percentage
- Time range filtering and bucket size configuration
- Span-level detail (change name, category, duration, result, retry count)
- Parallel efficiency metric (activity_time / wall_time)

## OUT OF SCOPE
- Real-time WebSocket streaming of activity data
- Historical cross-run comparison
- Cost/billing calculations from activity time
- Exporting activity data to external systems

### Requirement: Activity timeline endpoint

The system SHALL expose `GET /api/{project}/activity-timeline` that reconstructs activity spans from event sources and returns a structured timeline.

#### Scenario: Basic timeline request

- **WHEN** a client requests `GET /api/{project}/activity-timeline`
- **THEN** the response SHALL include `wall_time_ms` (first event to last event), `activity_time_ms` (sum of all span durations), `parallel_efficiency` (activity_time / wall_time ratio), `spans` (array of activity spans), and `breakdown` (per-category summary sorted by total time descending)

#### Scenario: Time range filtering

- **WHEN** a client requests `GET /api/{project}/activity-timeline?from=2026-04-08T10:00:00&to=2026-04-08T12:00:00`
- **THEN** only spans overlapping the requested time range SHALL be included
- **AND** spans partially outside the range SHALL be clipped to the range boundaries

#### Scenario: No events exist

- **WHEN** no event files exist for the project
- **THEN** the response SHALL return `{ "wall_time_ms": 0, "activity_time_ms": 0, "parallel_efficiency": 0, "spans": [], "breakdown": [] }`

### Requirement: Span reconstruction from events

The system SHALL reconstruct typed activity spans by correlating start/end events from multiple sources.

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

#### Scenario: Idle span from gap detection

- **WHEN** no activity events exist for any change between T1 and T2
- **AND** the gap exceeds 60 seconds
- **THEN** an `idle` span SHALL be produced with `start=T1`, `end=T2`

#### Scenario: Gate retry produces multiple spans

- **WHEN** a gate runs, fails, and retries
- **THEN** each attempt SHALL produce a separate span with a `retry` field indicating the attempt number
- **AND** the `result` field SHALL be `fail` for failed attempts and `pass` for the final successful attempt

### Requirement: Multi-source event merging

The system SHALL merge events from orchestration events JSONL, sentinel events JSONL, and loop state files into a single chronological stream.

#### Scenario: Events from rotated archives included

- **WHEN** the orchestration events file has been rotated
- **AND** archived files exist matching the `from` parameter
- **THEN** the aggregator SHALL read archived files to include the full event history

#### Scenario: Sentinel events contribute to timeline

- **WHEN** sentinel events include `crash` and `restart` entries
- **THEN** `stall-recovery` spans SHALL be produced from crash to restart timestamps

#### Scenario: Loop state iteration boundaries

- **WHEN** ITERATION_START and ITERATION_END events exist for a change
- **THEN** they SHALL be used to refine `implementing` span boundaries within a step

### Requirement: Breakdown summary

The system SHALL compute a per-category breakdown from the reconstructed spans.

#### Scenario: Breakdown includes all categories with time

- **WHEN** the timeline contains spans across multiple categories
- **THEN** the breakdown SHALL list each category with `total_ms` (sum of span durations) and `pct` (percentage of total activity time)
- **AND** categories SHALL be sorted by `total_ms` descending

#### Scenario: Parallel spans counted independently

- **WHEN** two worktrees both have `implementing` spans overlapping in time
- **THEN** the breakdown for `implementing` SHALL sum both spans' durations
- **AND** `activity_time_ms` SHALL exceed `wall_time_ms`

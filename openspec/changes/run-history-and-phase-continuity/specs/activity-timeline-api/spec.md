## ADDED Requirements

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

#### Scenario: All-lineages mode
- **WHEN** the client calls the endpoint with `?lineage=__all__`
- **THEN** every span SHALL be returned regardless of lineage
- **AND** each span SHALL carry its `detail.spec_lineage_id` so the UI can regroup visually

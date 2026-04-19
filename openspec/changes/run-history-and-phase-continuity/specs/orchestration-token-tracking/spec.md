## ADDED Requirements

### Requirement: Token aggregation includes archived changes
The token aggregation surfaced by `/api/<project>/state` (top-level totals via `StatusHeader`) and `/api/<project>/llm-calls` (per-call list) SHALL include archived changes loaded from `state-archive.jsonl`.

#### Scenario: Archived-change totals
- **WHEN** `state-archive.jsonl` holds an entry with `input_tokens = 1_000_000`, `output_tokens = 50_000`, `cache_read_tokens = 900_000`, `cache_create_tokens = 100_000`
- **AND** the change's worktree has been cleaned up (`.removed.*`)
- **THEN** the top-level token totals SHALL include these values
- **AND** the Tokens panel row for the archived change SHALL display these values (not dashes)

#### Scenario: session_summary fallback for LLM calls
- **WHEN** an archive entry carries `session_summary` but its worktree session dir is absent
- **THEN** `/api/<project>/llm-calls` SHALL emit a synthetic aggregate "call" per archived change with `source = "archive_summary"`, `purpose = "aggregated"`, `tokens = <session_summary values>`, `timestamp = session_summary.last_call_ts`
- **AND** the call SHALL appear in the LLM Call Log with a distinguishing label (e.g., `(archived summary)`) so operators do not mistake it for a real per-call row

### Requirement: Token endpoints honour lineage filter
The token totals surfaced in `/api/<project>/state` and the call list from `/api/<project>/llm-calls` SHALL honour an optional `?lineage=<id>` parameter so the Tokens tab can display per-lineage cost.

#### Scenario: v1 totals while v2 runs
- **WHEN** the client calls `GET /api/<project>/state?lineage=docs/spec-v1.md`
- **THEN** the aggregated token totals SHALL include only v1-tagged changes (live + archived)
- **AND** v2's in-flight token usage SHALL NOT contaminate the v1 totals

#### Scenario: LLM calls filtered by lineage
- **WHEN** the client calls `GET /api/<project>/llm-calls?lineage=docs/spec-v1.md`
- **THEN** the returned call list SHALL contain only calls whose change's `spec_lineage_id` matches v1 (or whose event record carries that lineage tag)

### Requirement: Token panel renders archived rows explicitly
The Tokens panel (`web/src/components/TokensPanel.tsx`) SHALL render archived changes in the same table as live changes, visually marked so they are distinguishable from in-flight work.

#### Scenario: Archived row rendering
- **WHEN** the Tokens panel receives the project state with changes marked `_archived = true`
- **THEN** archived rows SHALL show the "(archived)" label next to the change name
- **AND** the row's token values SHALL come from the archive entry's aggregated fields, not from live session scans
- **AND** archived rows SHALL be sorted after live rows by default (archived history visible, not obscuring live activity)

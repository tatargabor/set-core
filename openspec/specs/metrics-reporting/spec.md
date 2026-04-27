# Metrics Reporting Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## MODIFIED Requirements

### Requirement: TUI metrics report command
The `set-memory metrics` command SHALL read the SQLite database and print a formatted text report to stdout, including usage rate from passive transcript matching.

#### Scenario: Default report (last 7 days)
- **WHEN** `set-memory metrics` is run without arguments
- **THEN** it SHALL display metrics for the last 7 days including: session count, total injections, total tokens burned, per-layer breakdown (count, avg tokens, avg relevance), relevance distribution (strong >0.7, partial 0.3-0.7, filtered <0.3), usage rate (passively matched/injected), legacy citation rate, dedup hit rate, empty injection rate

#### Scenario: Custom time range
- **WHEN** `set-memory metrics --since 30d` is run
- **THEN** it SHALL display metrics for the last 30 days

#### Scenario: JSON output
- **WHEN** `set-memory metrics --json` is run
- **THEN** it SHALL output the same data as structured JSON including `usage_rate`, `total_injected_ids`, `total_matched_ids` fields

#### Scenario: No data available
- **WHEN** `set-memory metrics` is run and the database is empty or does not exist
- **THEN** it SHALL print "No metrics data. Enable with: set-memory metrics --enable" and exit 0

## Requirements

### Requirement: SQLite schema migration for context IDs
The metrics SQLite schema SHALL add support for context_id storage and passive match tracking when first accessed after upgrade.

#### Scenario: Schema migration on existing DB
- **WHEN** `_get_db()` opens an existing metrics.db that lacks the `context_ids` column in `injections`
- **THEN** it SHALL run `ALTER TABLE injections ADD COLUMN context_ids TEXT DEFAULT '[]'` without data loss

#### Scenario: New mem_matches table creation
- **WHEN** `_get_db()` opens the database
- **THEN** it SHALL ensure a `mem_matches` table exists with columns: `id` (autoincrement), `session_id` (text), `context_id` (text, 4-char hex), `match_type` (text: "passive" or "explicit"), `UNIQUE(session_id, context_id)`

#### Scenario: Sessions table match columns
- **WHEN** `_get_db()` opens an existing metrics.db that lacks usage tracking columns in `sessions`
- **THEN** it SHALL add `matched_id_count INTEGER DEFAULT 0` and `injected_id_count INTEGER DEFAULT 0` columns

### Requirement: Flush session with passive match data
The `flush_session()` function SHALL accept and store passive match counts and injected ID counts.

#### Scenario: Session flush with passive matches
- **WHEN** `flush_session()` is called with a `mem_matches` list of `{context_id, match_type}` dicts
- **THEN** it SHALL insert each into `mem_matches` table and set `matched_id_count` in the sessions table

#### Scenario: Session flush with injected ID count
- **WHEN** `flush_session()` is called with metrics records containing `context_ids` arrays
- **THEN** it SHALL compute `injected_id_count` as the total number of unique context IDs across all records and store it in the sessions table

### Requirement: Usage rate in query_report
The `query_report()` function SHALL include usage rate data in its return value.

#### Scenario: Report with passive match data
- **WHEN** `query_report()` runs and sessions have `injected_id_count` > 0
- **THEN** the returned dict SHALL include `usage_rate` (float, 0-100), `total_injected_ids` (int), `total_matched_ids` (int)

#### Scenario: Report without context_id data
- **WHEN** `query_report()` runs and all sessions have `injected_id_count = 0`
- **THEN** the returned dict SHALL include `usage_rate: null`, `total_injected_ids: 0`, `total_matched_ids: 0`

### Requirement: Passive matching in transcript scan
The `scan_transcript_citations()` function SHALL accept injected content and perform keyword overlap matching in addition to legacy pattern detection.

#### Scenario: Passive match found
- **WHEN** transcript scanning finds an assistant message containing 2+ significant keywords from an injected memory with ID `a1b2`
- **THEN** it SHALL include `{"context_id": "a1b2", "match_type": "passive"}` in the returned matches list

#### Scenario: Legacy citation pattern found
- **WHEN** transcript scanning finds "From memory:" in an assistant message
- **THEN** it SHALL include `{"text": "...snippet...", "match_type": "explicit"}` as before (backward compatible)

#### Scenario: Both match types in same transcript
- **WHEN** a transcript contains both passive keyword matches and explicit "From memory:" patterns
- **THEN** both SHALL be returned, each with their respective match_type

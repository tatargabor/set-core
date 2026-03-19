## ADDED Requirements

### Requirement: Verify index command
`set-memory verify` SHALL call `verify_index()` and display the result showing total storage count, total indexed count, orphaned count, and health status.

#### Scenario: Healthy index
- **WHEN** user runs `set-memory verify`
- **AND** the index is healthy
- **THEN** stdout prints JSON with `{total_storage, total_indexed, orphaned_count, orphaned_ids, is_healthy: true}`

#### Scenario: Unhealthy index with orphans
- **WHEN** user runs `set-memory verify`
- **AND** some memories are not indexed
- **THEN** stdout prints JSON with `is_healthy: false` and lists orphaned IDs
- **AND** stderr suggests running `set-memory repair`

### Requirement: Recall by date range
`set-memory recall --since <ISO> --until <ISO>` SHALL call `recall_by_date(start, end)` to retrieve memories within a date range.

#### Scenario: Date range recall
- **WHEN** user runs `set-memory recall --since 2026-02-01 --until 2026-02-15`
- **THEN** stdout prints JSON array of memories created within that date range

#### Scenario: Since only (open-ended)
- **WHEN** user runs `set-memory recall --since 2026-02-01`
- **THEN** stdout prints JSON array of memories from that date to now

#### Scenario: Until only (open-ended)
- **WHEN** user runs `set-memory recall --until 2026-02-15`
- **THEN** stdout prints JSON array of memories from the beginning to that date

#### Scenario: Combined with query
- **WHEN** user runs `set-memory recall "auth errors" --since 2026-02-01`
- **THEN** the date filter is applied first, then semantic search within results

### Requirement: Forget by date range
`set-memory forget --since <ISO> --until <ISO>` SHALL call `forget_by_date(start, end)` to delete memories within a date range.

#### Scenario: Date range forget
- **WHEN** user runs `set-memory forget --since 2026-01-01 --until 2026-01-31 --confirm`
- **THEN** all memories within that date range are deleted
- **AND** stdout prints `{"deleted_count": N}`

#### Scenario: Forget by date without confirm
- **WHEN** user runs `set-memory forget --since 2026-01-01 --until 2026-01-31` (no `--confirm`)
- **THEN** the command exits with non-zero code
- **AND** stderr prints the count of memories that would be deleted and requires `--confirm`

### Requirement: Consolidation report command
`set-memory consolidation` SHALL call `consolidation_report()` and display memory strengthening/decay events, edge formation, and fact extraction statistics.

#### Scenario: Consolidation report
- **WHEN** user runs `set-memory consolidation`
- **THEN** stdout prints JSON consolidation report

#### Scenario: Consolidation with time range
- **WHEN** user runs `set-memory consolidation --since 2026-02-01`
- **THEN** stdout prints consolidation report filtered to events since that date

#### Scenario: Raw consolidation events
- **WHEN** user runs `set-memory consolidation --events`
- **THEN** stdout prints JSON array of raw consolidation events (from `consolidation_events()`)

### Requirement: Graph stats command
`set-memory graph-stats` SHALL call `graph_stats()` and display knowledge graph statistics.

#### Scenario: Graph stats output
- **WHEN** user runs `set-memory graph-stats`
- **THEN** stdout prints JSON with knowledge graph metrics (node count, edge count, etc.)

### Requirement: Flush command
`set-memory flush` SHALL call `flush()` to write any pending data to disk.

#### Scenario: Successful flush
- **WHEN** user runs `set-memory flush`
- **THEN** pending writes are flushed
- **AND** stdout prints `{"flushed": true}`

### Requirement: All new commands follow existing patterns
All new commands SHALL use `run_with_lock run_shodh_python`, pass data via `_SHODH_*` environment variables, and degrade gracefully when shodh-memory is not installed.

#### Scenario: New command with shodh-memory not installed
- **WHEN** shodh-memory is not installed
- **AND** user runs any new command (verify, consolidation, graph-stats, flush)
- **THEN** the command exits 0
- **AND** returns empty/null JSON

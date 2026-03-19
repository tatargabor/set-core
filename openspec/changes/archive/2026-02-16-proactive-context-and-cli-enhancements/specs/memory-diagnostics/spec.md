## ADDED Requirements

### Requirement: Stats command for memory quality diagnostics
The `set-memory stats` command SHALL display memory quality diagnostics including: type distribution, tag frequency distribution, importance histogram, noise ratio (percentage of memories with importance < 0.3), and total memory count. Output SHALL be human-readable by default, with `--json` for machine-readable output. If shodh-memory is not available, it SHALL exit silently with code 0.

#### Scenario: Stats with memories present
- **WHEN** `set-memory stats` is run
- **AND** the project has 50 memories
- **THEN** output includes type distribution (e.g., "Decision: 15, Learning: 25, Context: 10"), tag frequency (top 10 tags), importance histogram (5 buckets: 0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0), noise ratio, and total count

#### Scenario: Stats JSON output
- **WHEN** `set-memory stats --json` is run
- **THEN** output is a JSON object with keys: `total`, `type_distribution`, `tag_distribution`, `importance_histogram`, `noise_ratio`

#### Scenario: Stats without shodh-memory
- **WHEN** `set-memory stats` is run and shodh-memory is not available
- **THEN** the command exits 0 with no output

### Requirement: Cleanup command for low-value memory removal
The `set-memory cleanup` command SHALL call `forget_by_importance(threshold)` to remove memories below the given importance threshold. Default threshold SHALL be 0.2. The command SHALL display the count of deleted memories. A `--dry-run` flag SHALL show what would be deleted without actually deleting.

#### Scenario: Cleanup with default threshold
- **WHEN** `set-memory cleanup` is run
- **AND** 10 memories have importance < 0.2
- **THEN** 10 memories are deleted and output shows `{"deleted_count": 10}`

#### Scenario: Cleanup with custom threshold
- **WHEN** `set-memory cleanup --threshold 0.3` is run
- **THEN** all memories with importance < 0.3 are deleted

#### Scenario: Cleanup dry run
- **WHEN** `set-memory cleanup --dry-run` is run
- **THEN** output shows `{"would_delete": N, "dry_run": true}` without deleting any memories

#### Scenario: Cleanup without shodh-memory
- **WHEN** `set-memory cleanup` is run and shodh-memory is not available
- **THEN** the command exits 0 with no output

#### Scenario: Cleanup fallback when forget_by_importance unavailable
- **WHEN** `set-memory cleanup` is run
- **AND** the installed shodh-memory does not have `forget_by_importance()` method
- **THEN** the command SHALL list memories, filter by importance client-side, and call `forget(id)` for each match

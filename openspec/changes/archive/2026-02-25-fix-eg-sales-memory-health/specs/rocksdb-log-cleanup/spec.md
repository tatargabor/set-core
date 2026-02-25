## ADDED Requirements

### Requirement: wt-memory cleanup-logs subcommand
The `wt-memory` CLI SHALL provide a `cleanup-logs` subcommand that removes RocksDB `LOG.old.*` files older than 24 hours from the project's memory storage directories (`memories/` and `memory_index/`).

#### Scenario: Old LOG.old files removed
- **WHEN** `wt-memory cleanup-logs` is run
- **AND** 500 LOG.old files exist in `memories/`, 400 of which are older than 24 hours
- **THEN** the 400 old files SHALL be deleted
- **AND** the 100 recent files SHALL be preserved
- **AND** stdout SHALL report the count and bytes reclaimed

#### Scenario: No old files to clean
- **WHEN** `wt-memory cleanup-logs` is run
- **AND** all LOG.old files are less than 24 hours old
- **THEN** no files SHALL be deleted
- **AND** stdout SHALL report "0 files cleaned"

#### Scenario: Missing storage directory
- **WHEN** `wt-memory cleanup-logs` is run
- **AND** the storage directory does not exist
- **THEN** the command SHALL exit cleanly with no error

### Requirement: Automatic cleanup on Stop hook
The Stop handler in `wt-hook-memory` SHALL call `wt-memory cleanup-logs` once per session before running transcript extraction. This runs synchronously in the Stop handler (not the background extraction).

#### Scenario: Stop hook triggers cleanup
- **WHEN** the Stop event fires
- **THEN** `wt-memory cleanup-logs` SHALL run before `_stop_run_extraction_bg`
- **AND** cleanup failure SHALL NOT prevent transcript extraction from running

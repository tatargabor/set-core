## MODIFIED Requirements

### Requirement: Configuration via environment variables
The CLI SHALL read configuration from environment variables: `SHODH_HOST` (default `127.0.0.1`), `SHODH_PORT` (default `3030`), `SHODH_API_KEY` (default empty). If `SHODH_API_KEY` is set, an `Authorization: Bearer` header SHALL be included in all API requests. The `SHODH_STORAGE` variable SHALL configure the storage root (default `~/.local/share/set-core/memory`).

#### Scenario: Custom host and port
- **WHEN** `SHODH_HOST=192.168.1.5 SHODH_PORT=8080 set-memory health` is run
- **THEN** the health check targets `http://192.168.1.5:8080/health`

## ADDED Requirements

### Requirement: Sync subcommand in CLI dispatch
The `set-memory sync` command SHALL be dispatched from the main CLI entry point. It SHALL accept subcommands: `push`, `pull`, `status`, or no subcommand (which runs push + pull). The sync commands SHALL be listed in the usage help under a "Sync" section.

#### Scenario: Sync command dispatch
- **WHEN** `set-memory sync push` is run
- **THEN** the CLI dispatches to the sync push handler

#### Scenario: Sync in usage help
- **WHEN** `set-memory --help` is run
- **THEN** the output includes a "Sync" section listing `sync`, `sync push`, `sync pull`, and `sync status`

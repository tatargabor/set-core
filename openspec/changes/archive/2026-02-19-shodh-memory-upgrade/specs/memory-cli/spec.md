## MODIFIED Requirements

### Requirement: Installation via install.sh
The `set-memory` script SHALL be included in the `scripts` array of `install_scripts()` in `install.sh`, so it is symlinked to `~/.local/bin/` during installation. The CLI SHALL support the `audit`, `dedup`, `todo`, `verify`, `consolidation`, `graph-stats`, and `flush` subcommands in its main dispatch and usage text.

#### Scenario: Fresh install
- **WHEN** `install.sh` is run
- **THEN** `set-memory` is symlinked to `~/.local/bin/set-memory`

#### Scenario: Audit command dispatch
- **WHEN** `set-memory audit` is run
- **THEN** the main dispatch routes to `cmd_audit`

#### Scenario: Dedup command dispatch
- **WHEN** `set-memory dedup` is run
- **THEN** the main dispatch routes to `cmd_dedup`

#### Scenario: Todo command dispatch
- **WHEN** `set-memory todo` is run
- **THEN** the main dispatch routes to `cmd_todo`

#### Scenario: Verify command dispatch
- **WHEN** `set-memory verify` is run
- **THEN** the main dispatch routes to `cmd_verify`

#### Scenario: Consolidation command dispatch
- **WHEN** `set-memory consolidation` is run
- **THEN** the main dispatch routes to `cmd_consolidation`

#### Scenario: Graph-stats command dispatch
- **WHEN** `set-memory graph-stats` is run
- **THEN** the main dispatch routes to `cmd_graph_stats`

#### Scenario: Flush command dispatch
- **WHEN** `set-memory flush` is run
- **THEN** the main dispatch routes to `cmd_flush`

#### Scenario: Help text includes all new commands
- **WHEN** `set-memory --help` is run
- **THEN** the usage text lists `todo`, `verify`, `consolidation`, `graph-stats`, `flush` in appropriate sections

### Requirement: Updated usage text
The `usage()` function SHALL document all commands grouped logically including a Todo section.

#### Scenario: Help text includes todo section
- **WHEN** user runs `set-memory --help`
- **THEN** output includes a Todo section with `todo add`, `todo list`, `todo done`, `todo clear`
- **AND** includes Index section with `verify` alongside existing `repair`
- **AND** includes Introspection section with `consolidation`, `graph-stats`, `flush`

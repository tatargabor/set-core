## MODIFIED Requirements

### Requirement: Installation via install.sh
The `set-memory` script SHALL be included in the `scripts` array of `install_scripts()` in `install.sh`, so it is symlinked to `~/.local/bin/` during installation. The CLI SHALL support the `audit`, `dedup`, `metrics`, and `dashboard` subcommands in its main dispatch and usage text.

#### Scenario: Fresh install
- **WHEN** `install.sh` is run
- **THEN** `set-memory` is symlinked to `~/.local/bin/set-memory`

#### Scenario: Audit command dispatch
- **WHEN** `set-memory audit` is run
- **THEN** the main dispatch routes to `cmd_audit`

#### Scenario: Dedup command dispatch
- **WHEN** `set-memory dedup` is run
- **THEN** the main dispatch routes to `cmd_dedup`

#### Scenario: Metrics command dispatch
- **WHEN** `set-memory metrics` is run
- **THEN** the main dispatch routes to `cmd_metrics`

#### Scenario: Dashboard command dispatch
- **WHEN** `set-memory dashboard` is run
- **THEN** the main dispatch routes to `cmd_dashboard`

#### Scenario: Help text includes new commands
- **WHEN** `set-memory --help` is run
- **THEN** the usage text lists `metrics` and `dashboard` under a "Metrics & Reporting" section

# team-sync-traffic-guard Specification

## Purpose
Ensures Team Sync polling uses safe defaults and documentation warns about GitHub API traffic from aggressive sync intervals.

## Requirements
### Requirement: Safe Team Sync polling default
The `team.sync_interval_ms` default SHALL be 120000 (2 minutes). The README and GUI Settings tooltip SHALL warn that lower intervals increase GitHub API traffic.

#### Scenario: Default sync interval
- **WHEN** a fresh installation starts the Team Sync feature
- **THEN** the sync interval SHALL default to 120000ms (2 minutes)

#### Scenario: Configurable via Settings
- **WHEN** user opens Settings and adjusts the Team Sync interval
- **THEN** the interval MAY be set as low as 10000ms (10 seconds)
- **AND** the Settings UI SHALL show a note about GitHub traffic implications

### Requirement: GitHub traffic warning in documentation
The README Team Sync section SHALL include a warning that Team Sync generates git fetch+push operations on every sync cycle, and that aggressive intervals (under 30 seconds) can trigger GitHub rate limiting on busy teams.

#### Scenario: README contains traffic warning
- **WHEN** a user reads the Team Sync section in the README
- **THEN** they SHALL see a clear note about traffic generation and the recommended 2-minute default

#### Scenario: set-control-sync documented as traffic source
- **WHEN** a user reads the CLI Reference
- **THEN** `set-control-sync` SHALL be documented as an internal command that runs git fetch+push

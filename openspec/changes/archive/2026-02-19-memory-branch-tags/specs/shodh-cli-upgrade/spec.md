## ADDED Requirements

### Requirement: Migrate subcommand
`set-memory migrate` SHALL run all pending memory storage migrations. `set-memory migrate --status` SHALL display migration history.

#### Scenario: Run pending migrations
- **WHEN** user runs `set-memory migrate`
- **THEN** all pending migrations are applied in numbered order
- **AND** stdout prints each migration: `001: branch-tags — applied`

#### Scenario: Show migration status
- **WHEN** user runs `set-memory migrate --status`
- **THEN** stdout lists all known migrations with applied/pending status

#### Scenario: Migrate with shodh-memory not installed
- **WHEN** shodh-memory is not installed
- **AND** user runs `set-memory migrate`
- **THEN** the command exits 0 silently

### Requirement: Updated usage text
The `usage()` function SHALL include the `migrate` subcommand in its output.

#### Scenario: Help text includes migrate
- **WHEN** user runs `set-memory --help`
- **THEN** output includes the `migrate` and `migrate --status` commands

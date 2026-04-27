# Memory Migrations Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Migration framework with auto-run
`set-memory` SHALL include a versioned migration framework. Migrations are numbered functions (001, 002, ...) that transform memory data. Pending migrations SHALL run automatically on the first `set-memory` command that accesses storage, unless `--no-migrate` is passed.

#### Scenario: First run after upgrade with pending migrations
- **WHEN** user runs any `set-memory` command (e.g., `recall`, `remember`, `list`)
- **AND** there are unapplied migrations
- **THEN** pending migrations run automatically before the command executes
- **AND** stderr prints `Migrating memory storage... done (1 migration applied)`

#### Scenario: No pending migrations
- **WHEN** user runs any `set-memory` command
- **AND** all migrations have been applied
- **THEN** no migration runs and no output is produced

#### Scenario: Skip auto-migration
- **WHEN** user runs `set-memory recall "query" --no-migrate`
- **THEN** the command executes without running pending migrations

#### Scenario: Migration state tracking
- **WHEN** migration 001 completes successfully
- **THEN** a `.migrations` JSON file in the storage directory records `{"applied": ["001"], "last_run": "<ISO-timestamp>"}`

#### Scenario: Idempotent migrations
- **WHEN** migration 001 runs on a storage where it was already applied (e.g., `.migrations` file was deleted)
- **THEN** the migration completes without errors or duplicate modifications

### Requirement: Manual migrate subcommand
`set-memory migrate` SHALL run all pending migrations. `set-memory migrate --status` SHALL show which migrations have been applied.

#### Scenario: Manual migration run
- **WHEN** user runs `set-memory migrate`
- **THEN** all pending migrations are applied in order
- **AND** stdout prints each migration applied: `001: branch-tags — applied`

#### Scenario: No pending migrations
- **WHEN** user runs `set-memory migrate`
- **AND** all migrations are already applied
- **THEN** stdout prints `All migrations applied.`

#### Scenario: Migration status
- **WHEN** user runs `set-memory migrate --status`
- **THEN** stdout lists all known migrations with their status (applied/pending) and applied timestamp

### Requirement: Migration 001 — branch tags for existing memories
The first migration SHALL add a `branch:unknown` tag to every existing memory that does not already have a `branch:*` tag.

#### Scenario: Memory without branch tag
- **WHEN** migration 001 runs
- **AND** a memory has tags `["source:user", "change:foo"]`
- **THEN** the memory's tags become `["source:user", "change:foo", "branch:unknown"]`

#### Scenario: Memory already has branch tag
- **WHEN** migration 001 runs
- **AND** a memory has tags `["source:user", "branch:main"]`
- **THEN** the memory's tags are unchanged

#### Scenario: Memory with no tags
- **WHEN** migration 001 runs
- **AND** a memory has tags `[]`
- **THEN** the memory's tags become `["branch:unknown"]`

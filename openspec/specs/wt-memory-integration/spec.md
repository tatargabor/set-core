## ADDED Requirements

### Requirement: Memory seed file format
The system SHALL support a `set/knowledge/memory-seed.yaml` file containing project-essential memories to bootstrap new memory stores.

#### Scenario: Valid seed file
- **WHEN** a memory seed file exists at `set/knowledge/memory-seed.yaml`
- **THEN** it contains a `version` field (integer) and a `seeds` array
- **AND** each seed has `type` (Context, Decision, or Learning), `content` (string), and `tags` (comma-separated string)

#### Scenario: Seed file example
- **WHEN** a project maintains a seed file
- **THEN** it contains 10-30 essential memories covering: tech stack, key conventions, cross-cutting concerns, and known pitfalls

### Requirement: Auto-import seeds on project init
`set-project init` SHALL import memory seeds when the memory store is empty and a seed file exists.

#### Scenario: Fresh install with seeds
- **WHEN** `set-project init` runs
- **AND** `set/knowledge/memory-seed.yaml` exists
- **AND** the project's memory store is empty (no memories)
- **THEN** all seeds are imported into the memory store with `source:seed` appended to each seed's existing tags
- **AND** duplicate detection is based on content text only (ignoring tags and type)
- **AND** the output displays "Imported N memory seeds"

#### Scenario: Non-empty memory store
- **WHEN** `set-project init` runs
- **AND** the project's memory store already has memories
- **THEN** seeds are NOT auto-imported (to avoid duplicates)
- **AND** the output displays "Memory store not empty — skip seed import. Use 'set-memory seed' to force."

#### Scenario: No seed file
- **WHEN** `set-project init` runs
- **AND** `set/knowledge/memory-seed.yaml` does not exist
- **THEN** the seed import step is silently skipped

### Requirement: Explicit seed import command
`set-memory seed` SHALL import seeds from the seed file, skipping duplicates.

#### Scenario: Import with duplicate detection
- **WHEN** user runs `set-memory seed`
- **AND** `set/knowledge/memory-seed.yaml` exists
- **THEN** each seed is checked against existing memories by content hash
- **AND** only new seeds are imported
- **AND** the output displays "Imported N new seeds, skipped M existing"

#### Scenario: No seed file
- **WHEN** user runs `set-memory seed`
- **AND** `set/knowledge/memory-seed.yaml` does not exist
- **THEN** the command prints "No seed file found at set/knowledge/memory-seed.yaml"

### Requirement: Memory sync uses wt work directory
The `set-memory sync` commands SHALL use `set/.work/memory/` as the working directory for sync operations when the `wt/` directory exists.

#### Scenario: Sync push working files
- **WHEN** `set-memory sync push` runs
- **AND** `set/.work/` directory exists
- **THEN** the export JSON is written to `set/.work/memory/export.json`
- **AND** sync state is tracked in `set/.work/memory/.sync-state`
- **AND** the sync state is per-working-directory (each clone maintains independent sync state)

#### Scenario: Migrate existing sync state
- **WHEN** `set-memory sync push` or `pull` runs with `wt/` present
- **AND** `set/.work/memory/.sync-state` does not exist
- **AND** `.sync-state` exists in the legacy storage path (`~/.local/share/set-core/memory/<project>/`)
- **THEN** the legacy `.sync-state` is copied to `set/.work/memory/.sync-state`
- **AND** subsequent sync operations use the new location

#### Scenario: Sync pull staging
- **WHEN** `set-memory sync pull` runs
- **AND** `set/.work/` directory exists
- **THEN** pulled data is staged in `set/.work/memory/import-staging/`

#### Scenario: Fallback without wt directory
- **WHEN** sync commands run in a project without `wt/` directory
- **THEN** the existing behavior is preserved (temp dirs, memory store dir for state)

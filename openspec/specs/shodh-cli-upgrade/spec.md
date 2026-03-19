# shodh-cli-upgrade Specification

## Purpose
TBD - created by archiving change agent-insight-memory. Update Purpose after archive.
## Requirements
### Requirement: Forget single memory by ID
`set-memory forget <memory_id>` SHALL delete a single memory by its ID and print the result as JSON.

#### Scenario: Successful forget
- **WHEN** user runs `set-memory forget abc123`
- **THEN** the memory with ID `abc123` is deleted from storage
- **AND** stdout prints `{"deleted": true, "id": "abc123"}`

#### Scenario: Forget non-existent ID
- **WHEN** user runs `set-memory forget nonexistent`
- **THEN** the command exits 0 (graceful)
- **AND** stdout prints `{"deleted": false, "id": "nonexistent"}`

#### Scenario: Forget with shodh-memory not installed
- **WHEN** shodh-memory is not installed
- **AND** user runs `set-memory forget abc123`
- **THEN** the command exits 0 silently

### Requirement: Forget all memories with confirmation
`set-memory forget --all` SHALL delete all memories for the current project, but ONLY when `--confirm` flag is provided.

#### Scenario: Forget all with confirmation
- **WHEN** user runs `set-memory forget --all --confirm`
- **THEN** all memories for the current project are deleted
- **AND** stdout prints `{"deleted_count": N}`

#### Scenario: Forget all without confirmation
- **WHEN** user runs `set-memory forget --all` (without `--confirm`)
- **THEN** the command exits with non-zero code
- **AND** stderr prints an error requiring `--confirm`

### Requirement: Forget by age
`set-memory forget --older-than <days>` SHALL delete memories older than the specified number of days.

#### Scenario: Age-based forget
- **WHEN** user runs `set-memory forget --older-than 90`
- **THEN** all memories older than 90 days are deleted
- **AND** stdout prints `{"deleted_count": N}`

### Requirement: Forget by tags
`set-memory forget --tags <t1,t2>` SHALL delete memories matching the specified tags.

#### Scenario: Tag-based forget
- **WHEN** user runs `set-memory forget --tags change:old-feature,phase:apply`
- **THEN** all memories with those tags are deleted
- **AND** stdout prints `{"deleted_count": N}`

### Requirement: Forget by pattern
`set-memory forget --pattern <regex>` SHALL delete memories whose content matches the regex pattern.

#### Scenario: Pattern-based forget
- **WHEN** user runs `set-memory forget --pattern "TODO:.*temporary"`
- **THEN** all memories matching the pattern are deleted
- **AND** stdout prints `{"deleted_count": N}`

### Requirement: Enhanced recall with mode parameter
`set-memory recall` SHALL accept a `--mode` parameter to control the recall strategy.

#### Scenario: Hybrid recall mode
- **WHEN** user runs `set-memory recall "auth patterns" --mode hybrid`
- **THEN** the recall uses combined semantic + temporal search
- **AND** results are returned as JSON array

#### Scenario: Temporal recall mode
- **WHEN** user runs `set-memory recall "recent errors" --mode temporal`
- **THEN** the recall prioritizes time-based relevance

#### Scenario: Default mode is semantic
- **WHEN** user runs `set-memory recall "query"` without `--mode`
- **THEN** the recall uses semantic mode (current default behavior preserved)

### Requirement: Enhanced recall with tag filtering
`set-memory recall` SHALL accept a `--tags` parameter to filter results by tags.

#### Scenario: Tag-filtered recall
- **WHEN** user runs `set-memory recall "implementation" --tags change:add-auth`
- **THEN** results are filtered to only include memories with the `change:add-auth` tag
- **AND** semantic relevance is applied within the filtered set

#### Scenario: Multiple tag filter
- **WHEN** user runs `set-memory recall "errors" --tags change:add-auth,phase:apply`
- **THEN** results are filtered to memories matching both tags

### Requirement: Enhanced list with filters
`set-memory list` SHALL accept `--type` and `--limit` parameters.

#### Scenario: List filtered by type
- **WHEN** user runs `set-memory list --type Decision`
- **THEN** only memories with `experience_type: Decision` are returned

#### Scenario: List with limit
- **WHEN** user runs `set-memory list --limit 10`
- **THEN** at most 10 memories are returned

#### Scenario: List with both filters
- **WHEN** user runs `set-memory list --type Learning --limit 5`
- **THEN** at most 5 memories with `experience_type: Learning` are returned

### Requirement: Context summary command
`set-memory context` SHALL display a condensed summary of memories by category.

#### Scenario: Context summary without topic
- **WHEN** user runs `set-memory context`
- **THEN** stdout prints a JSON summary with decisions, learnings, and context categories

#### Scenario: Context summary with topic
- **WHEN** user runs `set-memory context "authentication"`
- **THEN** stdout prints a JSON summary filtered/focused on the given topic

### Requirement: Brain state command
`set-memory brain` SHALL display a 3-tier memory visualization (working/session/longterm).

#### Scenario: Brain state output
- **WHEN** user runs `set-memory brain`
- **THEN** stdout prints a JSON representation of the 3-tier memory state

### Requirement: Get single memory by ID
`set-memory get <memory_id>` SHALL retrieve and display a single memory by its ID.

#### Scenario: Successful get
- **WHEN** user runs `set-memory get abc123`
- **THEN** stdout prints the full memory JSON (content, type, tags, timestamp, etc.)

#### Scenario: Get non-existent ID
- **WHEN** user runs `set-memory get nonexistent`
- **THEN** stdout prints `null` or `{}`
- **AND** the command exits 0

### Requirement: Index health check
`set-memory health --index` SHALL check the integrity of the shodh-memory index.

#### Scenario: Healthy index
- **WHEN** user runs `set-memory health --index`
- **AND** the index is healthy
- **THEN** stdout prints the index health JSON from shodh-memory

#### Scenario: Basic health without --index
- **WHEN** user runs `set-memory health` (without `--index`)
- **THEN** behavior is unchanged (prints "ok" or exits non-zero)

### Requirement: Repair index command
`set-memory repair` SHALL repair the shodh-memory index integrity.

#### Scenario: Successful repair
- **WHEN** user runs `set-memory repair`
- **THEN** the index is repaired
- **AND** stdout prints the repair result JSON

### Requirement: All new commands follow existing patterns
All new CLI commands SHALL use `run_with_lock run_shodh_python` for database access, pass data via `_SHODH_*` environment variables, and degrade gracefully when shodh-memory is not installed.

#### Scenario: New command with shodh-memory not installed
- **WHEN** shodh-memory is not installed
- **AND** user runs any new command (forget, context, brain, get, repair)
- **THEN** the command exits 0
- **AND** returns empty/null JSON (not an error)

#### Scenario: Concurrent access protection
- **WHEN** two processes run `set-memory forget` and `set-memory recall` simultaneously
- **THEN** both commands complete successfully via flock serialization

### Requirement: Updated usage text
The `usage()` function SHALL document all new commands grouped logically.

#### Scenario: Help text includes new commands
- **WHEN** user runs `set-memory --help`
- **THEN** output includes sections for Forget/Cleanup, Introspection, and Maintenance commands
- **AND** includes enhanced options for recall and list


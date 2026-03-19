## ADDED Requirements

### Requirement: Export project memories to JSON
The system SHALL export all memories for the current project to a single JSON file containing a version header and all record data.

#### Scenario: Export to stdout
- **WHEN** user runs `set-memory export`
- **THEN** system outputs valid JSON to stdout with `version`, `format`, `project`, `exported_at`, `count`, and `records` fields

#### Scenario: Export to file
- **WHEN** user runs `set-memory export --output <path>`
- **THEN** system writes the JSON to the specified file path
- **AND** outputs nothing to stdout

#### Scenario: Export empty project
- **WHEN** user runs `set-memory export` on a project with no memories
- **THEN** system outputs valid JSON with `count: 0` and empty `records` array

#### Scenario: Export preserves all record fields
- **WHEN** system exports a memory record
- **THEN** the exported record SHALL contain `id`, `content`, `experience_type`, `tags`, `importance`, `created_at`, `last_accessed`, `access_count`, `is_anomaly`, `is_failure`, `compressed`, `metadata`, and `entities`

### Requirement: Import memories from JSON with dedup
The system SHALL import memories from a JSON export file, skipping any record that already exists in the target project.

#### Scenario: Import into empty project
- **WHEN** user runs `set-memory import <file>` on a project with no memories
- **THEN** all records from the file are imported
- **AND** each imported record has `metadata.original_id` set to the source record's `id`
- **AND** system outputs JSON with `imported` count equal to file record count and `skipped: 0`

#### Scenario: Skip by exact ID match
- **WHEN** an incoming record's `id` matches an existing record's `id` in the target project
- **THEN** system SHALL skip that record

#### Scenario: Skip by original_id match in target
- **WHEN** an incoming record's `id` matches an existing record's `metadata.original_id`
- **THEN** system SHALL skip that record (it was already imported before)

#### Scenario: Skip reverse import
- **WHEN** an incoming record has `metadata.original_id` that matches an existing record's `id` in the target project
- **THEN** system SHALL skip that record (it originated from the target)

#### Scenario: Skip double-import via original_id
- **WHEN** an incoming record has `metadata.original_id` that matches an existing record's `metadata.original_id`
- **THEN** system SHALL skip that record (same source, already imported)

#### Scenario: Roundtrip produces no duplicates
- **WHEN** project A exports, project B imports, project B exports, project A imports
- **THEN** project A SHALL contain no duplicate memories

#### Scenario: Import result output
- **WHEN** import completes
- **THEN** system outputs JSON with `imported`, `skipped`, and `errors` counts

### Requirement: Dry-run import preview
The system SHALL support a `--dry-run` flag on import that reports what would happen without writing any data.

#### Scenario: Dry-run shows counts
- **WHEN** user runs `set-memory import <file> --dry-run`
- **THEN** system outputs JSON with `would_import`, `would_skip`, and `dry_run: true`
- **AND** no records are written to the target project

### Requirement: Import validates file format
The system SHALL validate the import file before processing records.

#### Scenario: Invalid JSON
- **WHEN** user runs `set-memory import <file>` with a non-JSON file
- **THEN** system outputs an error message and exits with non-zero status

#### Scenario: Unknown version
- **WHEN** the import file has a `version` field that is not `1`
- **THEN** system outputs an error message about unsupported version and exits with non-zero status

#### Scenario: Missing format field
- **WHEN** the import file lacks the `format: "set-memory-export"` field
- **THEN** system outputs an error message and exits with non-zero status

### Requirement: Graceful degradation on export/import
The system SHALL follow the existing set-memory pattern of graceful degradation when shodh-memory is not installed.

#### Scenario: Export without shodh-memory
- **WHEN** shodh-memory is not installed and user runs `set-memory export`
- **THEN** system exits silently with exit code 0

#### Scenario: Import without shodh-memory
- **WHEN** shodh-memory is not installed and user runs `set-memory import <file>`
- **THEN** system exits silently with exit code 0

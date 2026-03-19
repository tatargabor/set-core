## MODIFIED Requirements

### Requirement: Remember command with graceful degradation
The `set-memory remember` command SHALL read content from stdin and POST it to `/api/remember` with the specified `--type` and optional `--tags`. Additionally, it SHALL accept `--metadata JSON` (arbitrary JSON object), `--failure` (boolean flag marking the memory as a failure case), and `--anomaly` (boolean flag marking the memory as anomalous). If shodh-memory is not running, the command SHALL exit silently with code 0 (no-op). The `--type` parameter is required; `--tags` accepts a comma-separated list.

#### Scenario: Remember with shodh-memory running
- **WHEN** content is piped to `set-memory remember --type Learning --tags repo,change`
- **THEN** the content is POSTed to `/api/remember` with the given type and tags, and the command exits 0

#### Scenario: Remember without shodh-memory
- **WHEN** content is piped to `set-memory remember --type Learning` and shodh-memory is not running
- **THEN** the command exits silently with code 0 (no error output)

#### Scenario: Remember with empty stdin
- **WHEN** empty content is piped to `set-memory remember --type Learning`
- **THEN** the command exits 0 without making any API call

#### Scenario: Remember with metadata
- **WHEN** content is piped to `set-memory remember --type Decision --metadata '{"source":"review","pr":42}'`
- **THEN** the metadata JSON object is passed to `remember()` as the `metadata` parameter

#### Scenario: Remember with failure flag
- **WHEN** content is piped to `set-memory remember --type Learning --failure`
- **THEN** the `is_failure=True` parameter is passed to `remember()`

#### Scenario: Remember with anomaly flag
- **WHEN** content is piped to `set-memory remember --type Learning --anomaly`
- **THEN** the `is_anomaly=True` parameter is passed to `remember()`

#### Scenario: Remember with all new flags combined
- **WHEN** content is piped to `set-memory remember --type Learning --tags debug --metadata '{"env":"prod"}' --failure --anomaly`
- **THEN** all parameters (type, tags, metadata, is_failure=True, is_anomaly=True) are passed to `remember()`

#### Scenario: Remember with invalid metadata JSON
- **WHEN** content is piped to `set-memory remember --type Learning --metadata 'not-json'`
- **THEN** the command prints an error to stderr and exits with code 1

### Requirement: Recall command with graceful degradation
The `set-memory recall` command SHALL POST a semantic search query to `/api/recall` with the specified query string and optional `--limit` (default 5). Additionally, it SHALL accept `--tags-only` (uses `recall_by_tags()` instead of semantic search for faster tag-based lookups) and `--min-importance FLOAT` (filters results to only include memories with importance >= the given threshold). Output SHALL be JSON to stdout. If shodh-memory is not running, the command SHALL output `[]` and exit 0.

#### Scenario: Recall with shodh-memory running
- **WHEN** `set-memory recall "query text" --limit 3` is run
- **THEN** the search results are printed as JSON to stdout

#### Scenario: Recall without shodh-memory
- **WHEN** `set-memory recall "query text"` is run and shodh-memory is not running
- **THEN** the command outputs `[]` and exits 0

#### Scenario: Recall with tags-only mode
- **WHEN** `set-memory recall --tags-only --tags change:auth,phase:apply` is run
- **THEN** the command calls `recall_by_tags()` instead of `recall()` for fast tag-based lookup

#### Scenario: Recall with min-importance filter
- **WHEN** `set-memory recall "query text" --min-importance 0.5` is run
- **THEN** results are filtered to only include memories with importance >= 0.5

#### Scenario: Recall tags-only fallback
- **WHEN** `set-memory recall --tags-only --tags t1,t2` is run
- **AND** the installed shodh-memory does not have `recall_by_tags()` method
- **THEN** the command falls back to `recall()` with the same tags filter and logs a warning

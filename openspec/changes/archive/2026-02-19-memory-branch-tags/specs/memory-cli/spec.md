## MODIFIED Requirements

### Requirement: Remember command with graceful degradation
The `set-memory remember` command SHALL read content from stdin and store it via shodh-memory with the specified `--type` and optional `--tags`. If shodh-memory is not installed, the command SHALL exit silently with code 0 (no-op). The `--type` parameter is required; `--tags` accepts a comma-separated list. The command SHALL automatically append a `branch:<current-branch>` tag based on `git branch --show-current`, unless the caller already provided a `branch:*` tag or no branch can be detected.

#### Scenario: Remember with shodh-memory running
- **WHEN** content is piped to `set-memory remember --type Learning --tags repo,change`
- **THEN** the content is stored with the given type and tags plus the auto-detected branch tag, and the command exits 0

#### Scenario: Remember without shodh-memory
- **WHEN** content is piped to `set-memory remember --type Learning` and shodh-memory is not installed
- **THEN** the command exits silently with code 0 (no error output)

#### Scenario: Remember with empty stdin
- **WHEN** empty content is piped to `set-memory remember --type Learning`
- **THEN** the command exits 0 without storing anything

### Requirement: Recall command with graceful degradation
The `set-memory recall` command SHALL perform a semantic search with the specified query string and optional `--limit` (default 5). When run inside a git repo on a named branch and without explicit `--tags`, recall SHALL boost results matching the current branch by issuing a branch-filtered query alongside the main query and merging results. Output SHALL be JSON to stdout. If shodh-memory is not installed, the command SHALL output `[]` and exit 0.

#### Scenario: Recall with shodh-memory running
- **WHEN** `set-memory recall "query text" --limit 3` is run
- **THEN** the search results are printed as JSON to stdout, with current-branch results prioritized

#### Scenario: Recall without shodh-memory
- **WHEN** `set-memory recall "query text"` is run and shodh-memory is not installed
- **THEN** the command outputs `[]` and exits 0

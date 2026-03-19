## ADDED Requirements

### Requirement: Health check command
The `set-memory health` command SHALL check if shodh-memory is reachable by sending a GET request to `/health` with a maximum timeout of 1 second. It SHALL return exit code 0 and print the response body on success, or exit code 1 on failure.

#### Scenario: Shodh-memory is running
- **WHEN** shodh-memory is running on the configured host and port
- **THEN** `set-memory health` returns exit code 0 and prints the health response

#### Scenario: Shodh-memory is not running
- **WHEN** shodh-memory is not reachable
- **THEN** `set-memory health` returns exit code 1 with no output

### Requirement: Remember command with graceful degradation
The `set-memory remember` command SHALL read content from stdin and POST it to `/api/remember` with the specified `--type` and optional `--tags`. If shodh-memory is not running, the command SHALL exit silently with code 0 (no-op). The `--type` parameter is required; `--tags` accepts a comma-separated list.

#### Scenario: Remember with shodh-memory running
- **WHEN** content is piped to `set-memory remember --type Learning --tags repo,change`
- **THEN** the content is POSTed to `/api/remember` with the given type and tags, and the command exits 0

#### Scenario: Remember without shodh-memory
- **WHEN** content is piped to `set-memory remember --type Learning` and shodh-memory is not running
- **THEN** the command exits silently with code 0 (no error output)

#### Scenario: Remember with empty stdin
- **WHEN** empty content is piped to `set-memory remember --type Learning`
- **THEN** the command exits 0 without making any API call

### Requirement: Recall command with graceful degradation
The `set-memory recall` command SHALL POST a semantic search query to `/api/recall` with the specified query string and optional `--limit` (default 5). Output SHALL be JSON to stdout. If shodh-memory is not running, the command SHALL output `[]` and exit 0.

#### Scenario: Recall with shodh-memory running
- **WHEN** `set-memory recall "query text" --limit 3` is run
- **THEN** the search results are printed as JSON to stdout

#### Scenario: Recall without shodh-memory
- **WHEN** `set-memory recall "query text"` is run and shodh-memory is not running
- **THEN** the command outputs `[]` and exits 0

### Requirement: Status command
The `set-memory status` command SHALL display the current configuration (host, port, base URL, API key presence) and whether shodh-memory is reachable.

#### Scenario: Status display
- **WHEN** `set-memory status` is run
- **THEN** configuration values and health status are printed to stdout

### Requirement: Configuration via environment variables
The CLI SHALL read configuration from environment variables: `SHODH_HOST` (default `127.0.0.1`), `SHODH_PORT` (default `3030`), `SHODH_API_KEY` (default empty). If `SHODH_API_KEY` is set, an `Authorization: Bearer` header SHALL be included in all API requests.

#### Scenario: Custom host and port
- **WHEN** `SHODH_HOST=192.168.1.5 SHODH_PORT=8080 set-memory health` is run
- **THEN** the health check targets `http://192.168.1.5:8080/health`

### Requirement: Installation via install.sh
The `set-memory` script SHALL be included in the `scripts` array of `install_scripts()` in `install.sh`, so it is symlinked to `~/.local/bin/` during installation.

#### Scenario: Fresh install
- **WHEN** `install.sh` is run
- **THEN** `set-memory` is symlinked to `~/.local/bin/set-memory`

# Local Config Specification

## Purpose

One uncommitted home for machine- and project-specific values — under the set-core config directory, outside every repository — so committed code reads them instead of inlining what the leak gate would refuse.

## Requirements

### Requirement: One resolution chain, and an unset value reads as unset
`set_orch.local_config.get(key, project)` SHALL resolve a value in a single documented order — the environment variable `SETCORE_<KEY>` (upper-cased, non-alphanumerics folded to underscores), then the project-scoped file, then the machine-scoped file, then the caller's default. A key missing at every level SHALL return the default (None unless given); it SHALL NOT raise and SHALL NOT log an error, because "unset" is an ordinary answer.

#### Scenario: The environment overrides the files
- **WHEN** `SETCORE_TOOLS_DIR` is set and the same key also exists in the project file
- **THEN** `get` SHALL return the environment value

#### Scenario: A key set nowhere
- **WHEN** the key exists in no source and a default of `"fallback"` is supplied
- **THEN** `get` SHALL return `"fallback"` without raising

### Requirement: Values live outside every repository
`set` SHALL write machine-scoped values to `<config-dir>/config.json` and project-scoped values to `<config-dir>/projects/<project>.json`, where `<config-dir>` is the existing set-core config directory and `<project>` comes from the same project-name resolver the runtime uses. It SHALL merge into the existing JSON rather than replace it, SHALL create files with owner-only permissions (0600) and the directory with 0700, and SHALL never write inside a repository.

#### Scenario: A project-scoped write
- **WHEN** `set("endpoint", "http://127.0.0.1:8123", project="p")` runs
- **THEN** the value SHALL land in the config directory's `projects/p.json`, merged beside any existing keys, and no file inside any repository SHALL change

#### Scenario: Another project does not see the value
- **WHEN** the key was set for project `p` and `get(key, project="q")` runs
- **THEN** `get` SHALL NOT return p's value

### Requirement: The CLI reads and writes the same chain
`set-config` SHALL expose `get <key>`, `set <key> <value>`, and `list`, honouring an optional `--project <name>`. `list` SHALL show which keys exist and which file each resolves from, and SHALL mask values — it SHALL print the shape of the configuration, not the values, for the same reason the leakscan prints pattern counts and not patterns.

#### Scenario: Listing never prints a value
- **WHEN** `set-config list` runs on a config holding at least one key
- **THEN** every value SHALL be masked (or omitted) and the source file of each key SHALL be shown

#### Scenario: A round trip
- **WHEN** `set-config set db_host localhost --project p` runs and then `set-config get db_host --project p`
- **THEN** the get SHALL print `localhost`

# v0-design-import Specification

## Purpose
TBD - created by archiving change tsconfig-and-gitignore-template-hardening. Update Purpose after archive.
## Requirements
### Requirement: set-design-import patches tsconfig exclude on every run

The `set-design-import` CLI SHALL patch the consumer project's `tsconfig.json["exclude"]` to include the canonical v0-export and backup patterns on every run that touches `v0-export/` — both full imports and `--regenerate-manifest`-only runs. The patch MUST be idempotent (no-op when patterns are already present) and additive (does not remove or reorder existing entries).

#### Scenario: Full import on a stale tsconfig patches exclude

- **WHEN** `set-design-import --git <url>` runs against a scaffold whose `tsconfig.json` has `"exclude": ["node_modules"]`
- **THEN** after the CLI exits successfully the `exclude` list contains `"node_modules"`, `"v0-export"`, `"v0-export.*"`, `"*.bak"`, `"*.bak.*"`
- **AND** an INFO log line names the entries that were added

#### Scenario: Regenerate-manifest on a stale tsconfig patches exclude

- **WHEN** `set-design-import --regenerate-manifest` runs against a scaffold whose `tsconfig.json` has `"exclude": ["node_modules"]`
- **THEN** after the CLI exits successfully the `exclude` list contains the four canonical v0-export patterns in addition to what was there before
- **AND** an INFO log line names the entries that were added

#### Scenario: Patch is idempotent when excludes already cover the patterns

- **WHEN** `set-design-import` runs against a scaffold whose `tsconfig.json` already lists `"v0-export"`, `"v0-export.*"`, `"*.bak"`, `"*.bak.*"` in its exclude array
- **THEN** the file on disk is byte-identical before and after the CLI run
- **AND** a DEBUG log line records that the patch was a no-op

#### Scenario: Patch preserves the order of pre-existing exclude entries

- **WHEN** the pre-patch exclude is `["node_modules", "dist", "v0-export"]`
- **THEN** the post-patch exclude preserves `"node_modules"`, `"dist"`, `"v0-export"` in that order and appends `"v0-export.*"`, `"*.bak"`, `"*.bak.*"` at the end

### Requirement: set-design-import degrades gracefully on malformed tsconfig

The patcher MUST tolerate a `tsconfig.json` that it cannot parse as strict JSON (e.g. contains JSON5 comments or trailing commas) by emitting a WARNING and continuing the rest of the import flow. It MUST NOT abort the CLI and MUST NOT rewrite the file on a parse failure.

#### Scenario: tsconfig with JSON5 comments triggers warning

- **WHEN** `set-design-import` runs against a scaffold whose `tsconfig.json` contains `// line comments` that are not valid JSON
- **THEN** the patcher logs a WARNING identifying the file and the parse error
- **AND** the file on disk is unchanged
- **AND** the rest of the import (manifest regeneration, quality validator) continues normally

#### Scenario: Missing tsconfig is tolerated

- **WHEN** `set-design-import` runs against a scaffold that has no `tsconfig.json` at the project root
- **THEN** the patcher logs a DEBUG line indicating tsconfig was not found
- **AND** the rest of the import continues normally


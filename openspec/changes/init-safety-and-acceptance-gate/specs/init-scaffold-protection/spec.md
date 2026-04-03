## ADDED Requirements

## IN SCOPE
- Manifest-based protected file annotation
- Content hash comparison to detect project modifications
- Additive YAML merge for config files marked with `merge: true`
- Backward-compatible manifest parsing (plain strings and object entries)

## OUT OF SCOPE
- Per-file CLI override flags (--force-file, --skip-file)
- Git-based modification detection
- Interactive prompts asking user whether to overwrite each file
- Protection for framework files (.claude/rules/, .claude/commands/) — these always overwrite

### Requirement: Protected file annotation in manifest
The template `manifest.yaml` SHALL support annotating files with `protected: true` to indicate scaffold files that should not be overwritten during re-init if the project has modified them.

#### Scenario: Manifest with protected files
- **WHEN** `manifest.yaml` contains entries like `{path: "next.config.js", protected: true}`
- **THEN** `_resolve_file_list()` SHALL return `FileEntry` objects with `protected=True` for those files

#### Scenario: Backward compatible plain string entries
- **WHEN** `manifest.yaml` contains plain string entries (e.g., `- .gitignore`)
- **THEN** `_resolve_file_list()` SHALL treat them as `FileEntry(path=".gitignore", protected=False, merge=False)`

#### Scenario: Mixed format manifest
- **WHEN** `manifest.yaml` contains both plain strings and object entries
- **THEN** `_resolve_file_list()` SHALL parse each entry according to its type

### Requirement: Skip protected files when content differs
During re-init with `--force`, files marked `protected: true` SHALL be skipped if the existing file content differs from the template. If the content matches the template exactly, the file SHALL be overwritten (it has not been modified by the project).

#### Scenario: Protected file modified by project
- **WHEN** re-init runs with `--force`
- **AND** a protected file exists in the project
- **AND** the file's SHA256 hash differs from the template file's SHA256 hash
- **THEN** the file SHALL NOT be overwritten
- **AND** the status message SHALL say `Skipped (protected): <path>`

#### Scenario: Protected file unchanged from template
- **WHEN** re-init runs with `--force`
- **AND** a protected file exists in the project
- **AND** the file's SHA256 hash matches the template file's SHA256 hash
- **THEN** the file SHALL be overwritten with the template version
- **AND** the status message SHALL say `Overwritten: <path>`

#### Scenario: Protected file does not exist yet
- **WHEN** re-init runs and a protected file does not exist in the project
- **THEN** the file SHALL be deployed normally
- **AND** the status message SHALL say `Deployed: <path>`

### Requirement: Additive YAML merge for config files
Files marked with `merge: true` in the manifest SHALL use additive YAML merge during re-init instead of overwrite. New keys from the template are added; existing keys are preserved.

#### Scenario: Config file with new keys in template
- **WHEN** re-init runs with `--force`
- **AND** a merge-enabled config file exists with keys `{a: 1, b: 2}`
- **AND** the template has keys `{a: 99, b: 88, c: 3}`
- **THEN** the resulting file SHALL contain `{a: 1, b: 2, c: 3}`

#### Scenario: Config file matches template
- **WHEN** re-init runs and the config file has all keys from the template
- **THEN** the file SHALL not be modified

#### Scenario: Config file does not exist
- **WHEN** re-init runs and the merge-enabled config file does not exist
- **THEN** the template file SHALL be copied as-is

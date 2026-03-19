## Requirements

### Requirement: Arithmetic operations must be safe under set -e
All `(( var++ ))` and `(( var-- ))` expressions in `bin/wt-hook-memory` SHALL use `|| true` to prevent `set -e` from terminating the process when the expression evaluates to 0.

#### Scenario: Counter increment from zero
- **GIVEN** a counter variable initialized to 0
- **WHEN** the counter is incremented with `(( count++ )) || true`
- **THEN** the script SHALL continue execution regardless of the pre-increment value

#### Scenario: Background extraction completes
- **GIVEN** a Stop event with a valid transcript path
- **WHEN** `_stop_run_extraction_bg` runs in the background
- **THEN** `_stop_migrate_staged` SHALL complete without crashing
- **AND** `_stop_raw_filter` SHALL execute afterward
- **AND** the extraction log SHALL contain a "Raw filter complete" entry

### Requirement: Commit extraction content uses character-safe truncation
All content truncation in `_stop_commit_extraction()` (lines 1236, 1259) SHALL use bash substring operations (`${var:0:N}`) or `cut -c1-N` instead of `head -c N`. Content piped to `set-memory remember` SHALL be valid UTF-8.

#### Scenario: Code map with non-ASCII file paths
- **WHEN** a commit touches files with non-ASCII characters in their path
- **AND** the code map content exceeds the 400-char limit
- **THEN** truncation SHALL occur at a character boundary
- **AND** the saved memory SHALL be valid UTF-8

### Requirement: Staged file migration content sanitization
The `_stop_migrate_staged()` function SHALL sanitize content read from staged files before passing to `set-memory remember`. Content SHALL be validated as UTF-8, with invalid bytes replaced by U+FFFD.

#### Scenario: Staged file with corrupted encoding
- **WHEN** a staged file from the old Haiku era contains byte sequences that are not valid UTF-8
- **THEN** the migration SHALL replace invalid bytes with `�`
- **AND** the memory SHALL be saved successfully
- **AND** the staged file SHALL be cleaned up afterward

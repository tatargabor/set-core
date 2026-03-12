## MODIFIED Requirements

### Requirement: Platform-portable stat usage
All `stat` calls in orchestration code SHALL work on both Linux (GNU coreutils) and macOS (BSD). The system SHALL use a fallback chain: `stat -c %Y` (Linux) falling back to `stat -f %m` (macOS).

#### Scenario: File mtime on Linux
- **WHEN** `stat -c %Y "$file"` is called on Linux
- **THEN** the epoch timestamp is returned

#### Scenario: File mtime on macOS
- **WHEN** `stat -c %Y "$file"` fails on macOS
- **THEN** the fallback `stat -f %m "$file"` is used and returns the epoch timestamp

#### Scenario: stat failure on both platforms
- **WHEN** both stat variants fail (e.g., file doesn't exist)
- **THEN** `0` is returned as default

### Requirement: Platform-portable grep patterns
All `grep` calls in orchestration code SHALL use POSIX-compatible flags. `grep -P` (Perl regex) SHALL NOT be used.

#### Scenario: Non-portable grep replaced
- **WHEN** `grep -oP '\d+'` was used for digit extraction
- **THEN** it is replaced with `grep -oE '[0-9]+'` or equivalent POSIX pattern

### Requirement: Functions do not change working directory
Functions in orchestration code SHALL NOT use bare `cd` that permanently changes the caller's working directory. They SHALL use either `git -C` for git operations or subshells `(cd ... && ...)` for directory-scoped work.

#### Scenario: git operations use -C flag
- **WHEN** a function needs to run git in a worktree
- **THEN** it uses `git -C "$wt_path" ...` instead of `cd "$wt_path" && git ...`

#### Scenario: Non-git directory operations use subshell
- **WHEN** a function must change directory for non-git operations
- **THEN** it wraps the work in a subshell `(cd "$dir" && ...)`

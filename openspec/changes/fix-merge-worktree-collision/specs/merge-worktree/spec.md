## ADDED Requirements

### Requirement: set-merge accepts explicit worktree path

The `set-merge` command SHALL accept a `--worktree <path>` option. When provided, the command SHALL use that path directly and skip name-based discovery.

#### Scenario: Explicit worktree path accepted
- **WHEN** user runs `set-merge foo --worktree /repos/acme-wt-foo-2`
- **THEN** `set-merge` SHALL use `/repos/acme-wt-foo-2` as the worktree path
- **AND** SHALL NOT call `find_existing_worktree`

#### Scenario: Explicit path does not exist
- **WHEN** `--worktree /some/missing/path` is given
- **AND** the path does not exist or is not a directory
- **THEN** the command SHALL exit with a non-zero status and an error message naming the bad path

#### Scenario: Explicit path is not a registered git worktree
- **WHEN** `--worktree <path>` points at a directory that is not listed by `git worktree list --porcelain`
- **THEN** the command SHALL exit with a non-zero status and an error message clarifying that the directory is not a worktree

#### Scenario: No --worktree flag — discovery fallback
- **WHEN** user runs `set-merge foo` without `--worktree`
- **THEN** `find_existing_worktree` SHALL be called as before
- **AND** the discovery result SHALL be used to locate the worktree

### Requirement: set-merge help documents --worktree

The `set-merge --help` output SHALL list `--worktree <path>` among the options with a one-line description.

#### Scenario: Help lists the flag
- **WHEN** user runs `set-merge --help`
- **THEN** the output SHALL include `--worktree <path>` and a short description such as "use this explicit worktree path instead of discovering by name"

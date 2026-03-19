## ADDED Requirements

### Requirement: Sync push exports memory to git orphan branch
The `set-memory sync push` command SHALL export all project memories to a `set-memory` orphan branch on the git remote, under a `<user>/<machine>/memories.json` path. The user identifier SHALL be derived from `git config user.name` (lowercased, spaces replaced with hyphens), with `whoami` as fallback. The machine identifier SHALL be `hostname -s` (lowercased).

#### Scenario: First push creates orphan branch
- **WHEN** `set-memory sync push` is run and the `set-memory` branch does not exist on the remote
- **THEN** the command creates an orphan branch named `set-memory`
- **AND** commits the export file at `<user>/<machine>/memories.json`
- **AND** pushes to the remote

#### Scenario: Subsequent push updates existing file
- **WHEN** `set-memory sync push` is run and the `set-memory` branch already exists
- **THEN** the command updates `<user>/<machine>/memories.json` with the current full export
- **AND** commits and pushes to the remote

#### Scenario: Push skips when nothing changed
- **WHEN** `set-memory sync push` is run and the export content hash matches the last push hash in `.sync-state`
- **THEN** the command prints "Nothing to push." and exits without any git operations

### Requirement: Sync pull imports memory from other users/machines
The `set-memory sync pull` command SHALL fetch the `set-memory` branch from the remote and import all `memories.json` files belonging to OTHER users/machines (not the current user/machine). Import SHALL use the existing `set-memory import` deduplication logic.

#### Scenario: Pull imports from other team members
- **WHEN** `set-memory sync pull` is run and the remote has files from other users
- **THEN** the command imports each foreign `<user>/<machine>/memories.json`
- **AND** prints import results per source (e.g., "alice/workstation: 12 new, 45 skipped")

#### Scenario: Pull skips when remote unchanged
- **WHEN** `set-memory sync pull` is run and the remote `set-memory` branch HEAD matches `last_pull_commit` in `.sync-state`
- **THEN** the command prints "Up to date." and exits without importing

#### Scenario: Pull with no sync branch
- **WHEN** `set-memory sync pull` is run and the `set-memory` branch does not exist on the remote
- **THEN** the command prints "No sync branch found. Run 'set-memory sync push' first." and exits with code 0

#### Scenario: Selective pull from specific source
- **WHEN** `set-memory sync pull --from alice/workstation` is run
- **THEN** only the specified source's `memories.json` is imported

### Requirement: Sync command combines push and pull
The `set-memory sync` command (no subcommand) SHALL execute push followed by pull in sequence.

#### Scenario: Full sync
- **WHEN** `set-memory sync` is run
- **THEN** push is performed first, then pull
- **AND** output shows results of both operations

### Requirement: Sync status shows sync state
The `set-memory sync status` command SHALL display the current sync state including last push/pull timestamps and what sources are available on the remote branch.

#### Scenario: Status with prior syncs
- **WHEN** `set-memory sync status` is run and `.sync-state` exists
- **THEN** the command shows last push time, last pull time, and lists all `<user>/<machine>` entries on the remote branch

#### Scenario: Status with no prior syncs
- **WHEN** `set-memory sync status` is run and no `.sync-state` exists
- **THEN** the command prints "Never synced." and lists remote entries if the branch exists

### Requirement: Sync state tracking via .sync-state file
The sync commands SHALL maintain a `.sync-state` JSON file at `~/.local/share/set-core/memory/<project>/.sync-state` to track the last push export hash and the last pull remote commit hash. This file is used to avoid unnecessary git operations.

#### Scenario: State file created on first sync
- **WHEN** a sync push or pull completes successfully for the first time
- **THEN** a `.sync-state` file is created with the relevant hash and timestamp

#### Scenario: State file updated on subsequent syncs
- **WHEN** a sync push or pull completes successfully
- **THEN** the `.sync-state` file is updated with the new hash and timestamp

### Requirement: Sync uses temporary directory for push
The push operation SHALL use a temporary directory for git operations (clone, commit, push) and clean it up afterward. The user's working tree SHALL NOT be affected by sync operations.

#### Scenario: Working tree unaffected by push
- **WHEN** `set-memory sync push` is run from a worktree with uncommitted changes
- **THEN** the push completes without modifying the working tree
- **AND** `git status` in the working tree shows the same state as before

### Requirement: Sync pull uses git show for file extraction
The pull operation SHALL use `git fetch` + `git show` to extract files from the remote branch without creating a full checkout. This minimizes disk usage and avoids working tree interference.

#### Scenario: Pull extracts files efficiently
- **WHEN** `set-memory sync pull` is run
- **THEN** files are extracted via `git show origin/set-memory:<path>` to temp files
- **AND** no checkout of the `set-memory` branch is created

### Requirement: Graceful degradation for sync commands
Sync commands SHALL fail gracefully with clear error messages when preconditions are not met.

#### Scenario: No git remote
- **WHEN** `set-memory sync push` is run and no git remote named `origin` exists
- **THEN** the command prints "Error: no git remote 'origin' found" and exits with code 1

#### Scenario: Not a git repository
- **WHEN** `set-memory sync push` is run outside a git repository
- **THEN** the command prints "Error: not a git repository" and exits with code 1

#### Scenario: Shodh-memory not installed
- **WHEN** `set-memory sync push` is run and shodh-memory is not installed
- **THEN** the command exits silently with code 0 (consistent with other commands)

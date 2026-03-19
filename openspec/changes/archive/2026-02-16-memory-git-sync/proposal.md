## Why

Multiple developers work on the same project and need to share shodh-memory across machines and team members. The existing `set-memory export/import` works but requires manually copying files. A git-based sync using an orphan branch would make sharing seamless — one command to push, one to pull — while keeping the existing offline export/import intact.

## What Changes

- Add `set-memory sync push` command: exports memory to a `set-memory` orphan branch under `<user>/<machine>/memories.json`, commits and pushes
- Add `set-memory sync pull` command: fetches the branch, imports all other users'/machines' files (existing dedup prevents duplicates)
- Add `set-memory sync` command: push + pull in one step
- Add `set-memory sync status` command: show last sync timestamps, what's on the branch
- Local `.sync-state` file tracks last push hash and last pull commit to avoid unnecessary git operations
- Push skips entirely (0 network ops) if local memory hasn't changed since last push
- Pull skips import if remote branch hasn't changed since last pull
- Existing `set-memory export` and `set-memory import` remain unchanged for offline use

## Capabilities

### New Capabilities
- `memory-git-sync`: Git-based memory synchronization via orphan branch with user/machine namespacing and delta detection

### Modified Capabilities
- `memory-cli`: Add `sync` subcommand family (push/pull/status) to the existing CLI

## Impact

- **Code**: `bin/set-memory` — new `sync` subcommand with push/pull/status
- **Storage**: New `.sync-state` file in `~/.local/share/set-core/memory/<project>/`
- **Git**: Creates `set-memory` orphan branch on remote (no interference with code branches)
- **Dependencies**: None — uses only git CLI (already a dependency)
- **Existing functionality**: Export/import commands unchanged, fully backward compatible

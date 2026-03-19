## Why

Memories are stored in a flat per-project pool with no branch context. When working across multiple worktrees/branches in parallel, there's no way to know which branch produced a memory, prioritize current-branch knowledge during recall, or handle the lifecycle when branches merge or get dropped. Adding branch metadata via tags (not storage separation) preserves the instant cross-branch knowledge sharing that makes the memory system valuable, while adding useful context.

Additionally, as the memory schema evolves (this being the first example), there's no migration system to transform existing data — changes require manual intervention or data loss.

## What Changes

- `set-memory remember` automatically appends a `branch:<current-branch>` tag to every new memory
- `set-memory recall` boosts relevance of memories tagged with the current branch (others still returned)
- New `set-memory migrate` subcommand with a versioned migration framework
- First migration: tags existing memories with `branch:unknown`
- Migrations run automatically on first use after upgrade (with `--no-migrate` escape hatch)

## Capabilities

### New Capabilities
- `memory-branch-tags`: Auto-tagging memories with branch context and branch-aware recall boosting
- `memory-migrations`: Versioned migration framework for memory storage schema evolution

### Modified Capabilities
- `memory-cli`: remember command gains auto-tagging; recall gains branch boost behavior
- `shodh-cli-upgrade`: New `migrate` subcommand added to CLI surface

## Impact

- `bin/set-memory`: remember, recall, and new migrate subcommand
- `bin/wt-hook-memory-save`: may need branch tag injection
- `bin/wt-hook-memory-recall`: may leverage branch context for better queries
- Existing memories: retroactively tagged via migration (non-destructive)
- Sync: no changes needed — tags are already part of the export format

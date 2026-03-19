## Context

Memories are stored per-project in a flat shodh-memory pool at `~/.local/share/set-core/memory/<project>/`. The `resolve_project()` function already normalizes worktree paths to the main repo name, so all worktrees share one pool. Tags are stored as string arrays on each memory record and flow through export/import/sync unchanged.

The `cmd_remember` function reads `--tags` as comma-separated values and converts them to a JSON array via `jq`. The `cmd_recall` function passes tags to shodh-memory's `m.recall()` which supports tag-based filtering.

There is no migration system — the only versioning is `version: 1` in the export format, and a legacy storage path detection in `get_storage_path()`.

## Goals / Non-Goals

**Goals:**
- Auto-tag every new memory with `branch:<current-branch>` without requiring caller changes
- Boost recall relevance for current-branch memories while still returning cross-branch results
- Introduce a migration framework that can evolve memory data across versions
- Retroactively tag existing memories via the first migration

**Non-Goals:**
- Separate storage per branch (explored and rejected — kills cross-branch knowledge sharing)
- Automatic memory merging on `git merge` (tags already flow naturally)
- Changes to the sync protocol (tags are already synced)
- Branch-based access control or isolation

## Decisions

### Decision 1: Auto-tag in `cmd_remember` (not in hooks)

**Choice**: Inject `branch:<name>` tag inside `cmd_remember` itself, after parsing user-provided tags.

**Alternative**: Add branch tagging in `wt-hook-memory-save` or in CLAUDE.md instructions.

**Rationale**: `cmd_remember` is the single entry point for all memory creation — hooks, ambient CLAUDE.md, manual CLI use. Tagging here guarantees 100% coverage with zero caller changes.

### Decision 2: Branch detection via `git branch --show-current`

**Choice**: Use `git branch --show-current` to get the current branch name at remember-time.

**Alternative**: Use `git rev-parse --abbrev-ref HEAD` (same result but more complex for detached HEAD).

**Rationale**: `--show-current` returns empty string for detached HEAD (clean no-op), is simpler, and is available in git 2.22+ (2019). If empty or not in a git repo, skip the auto-tag silently.

### Decision 3: Branch tag format `branch:<name>`

**Choice**: Use `branch:` prefix with the full branch name, e.g., `branch:change/shodh-memory-integration`, `branch:master`.

**Alternative**: Normalize branch names (replace `/` with `-`).

**Rationale**: Keep the exact git branch name for clarity. Tags are just strings — slashes work fine. Consistent with existing tag conventions (`change:`, `phase:`, `source:`).

### Decision 4: Recall boost via double-query strategy

**Choice**: When recalling, issue two queries: (1) tag-filtered for current branch with half the limit, (2) unfiltered with full limit. Merge results, deduplicate by ID, branch-tagged first.

**Alternative A**: Single query with post-processing reranking.
**Alternative B**: Modify shodh-memory's recall to support tag boosting natively.

**Rationale**: Alternative A can't boost if branch results don't appear in top-N. Alternative B requires changes to the shodh-memory library. The double-query approach works with the existing API: branch-specific results appear first, then general results fill remaining slots.

### Decision 5: File-based migration framework

**Choice**: Store migrations as numbered functions (`migrate_001_branch_tags`) in `set-memory` itself. Track applied migrations in a `.migrations` JSON file in the storage directory. Run pending migrations automatically on first command that accesses storage.

**Alternative A**: External migration scripts in `bin/`.
**Alternative B**: Migration as a separate tool (`set-memory-migrate`).

**Rationale**: Keeping migrations inside `set-memory` ensures they run automatically — no manual step needed after upgrade. The `.migrations` file is simple and local. Functions are easy to add for future migrations.

### Decision 6: First migration tags existing memories with `branch:unknown`

**Choice**: Migration 001 iterates all existing memories and adds `branch:unknown` tag to any memory that has no `branch:*` tag.

**Alternative**: Tag with `branch:master` (assume they came from master).

**Rationale**: `branch:unknown` is honest — we don't know which branch created them. It's still a valid tag for filtering ("show me pre-migration memories"). New memories will always have accurate branch tags.

## Branch & Worktree Scenarios

| # | Scenario | Branch/WT state | Remember | Recall | Sync | Result |
|---|---|---|---|---|---|---|
| 1 | Normal work on master | `master`, main repo | tag: `branch:master` | boost: master | push/pull: tag included | ✅ simple |
| 2 | Feature branch | `change/xyz`, main repo | tag: `branch:change/xyz` | boost: change/xyz, master memories also returned | sync: tag included | ✅ branch context preserved |
| 3 | Worktree A (master) | master, wt | tag: `branch:master` | boost: master | shared pool | ✅ |
| 4 | Worktree B (feature) | `change/xyz`, wt | tag: `branch:change/xyz` | boost: change/xyz + cross-branch | shared pool | ✅ instant cross-wt sharing |
| 5 | Parallel wt's, B learns | A=master, B=change/xyz | B saves: `branch:change/xyz` | A recalls → B's memories returned (lower prio) | n/a (local) | ✅ knowledge instantly available |
| 6 | Merge branch→master | `change/xyz` → master | memories keep `branch:change/xyz` tag | on master: not boosted but findable | sync: unchanged | ✅ knowledge preserved |
| 7 | Branch dropped (no merge) | `change/xyz` deleted | memories persist with `branch:change/xyz` tag | from other branch: low prio but accessible | sync: unchanged | ✅ learnings not lost |
| 8 | Detached HEAD | rebase, bisect | no branch tag | recall: no boost (flat) | n/a | ✅ graceful fallback |
| 9 | Not a git repo | `$PROJECT` set manually | no branch tag | recall: no boost | n/a | ✅ graceful fallback |
| 10 | Sync to other machine | machine A → push, B → pull | tags exported | machine B: branch boost if same branch | user/machine namespacing | ✅ tag context preserved |
| 11 | Pre-migration memories | before migration | no branch tag | migration 001: `branch:unknown` | sync: unknown tag exported | ✅ migration handles it |
| 12 | Caller explicit branch tag | user passes `--tags branch:custom` | no duplicate auto-tag | boost on custom branch | n/a | ✅ user override respected |

## Risks / Trade-offs

- **[Risk] Auto-tag adds overhead to every remember call** → Minimal: one `git branch --show-current` call (~5ms). Already running git commands in `resolve_project()`.
- **[Risk] Double-query recall is slower** → Two shodh-memory queries instead of one. Mitigated by halving the limit on the first query. Total results stay within requested limit.
- **[Risk] Migration on first use could be slow with many memories** → Migration 001 reads all memories and updates tags. For typical project sizes (<500 memories), this is sub-second. Add progress indicator for large sets.
- **[Risk] `.migrations` file could get corrupted** → Use atomic write (write to temp, rename). If missing, re-run all migrations (they're idempotent).

## Migration Plan

1. Add migration framework and migration 001 to `set-memory`
2. On first `set-memory` command after upgrade, migrations run automatically
3. `set-memory migrate` subcommand also available for manual/forced runs
4. `set-memory migrate --status` shows applied migrations
5. Rollback: migrations are additive (adding tags), no destructive changes. "Rollback" = remove `branch:unknown` tags via `set-memory forget --tags branch:unknown` if needed.

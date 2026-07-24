## Why

The project registry accumulates entries that nothing removes. Measured 2026-07-24 on
`~/.config/set-core/projects.json`: **50 entries, of which 12 point at directories that no
longer exist** — temp-directory scaffolds and short-lived test fixtures from earlier
sessions — and ~17 more are old E2E runs under the framework's own `e2e-runs/` root.
The dashboard lists all of them, so the projects actually being worked on are buried. In
parallel, `git worktree list --porcelain` reports **10 orphaned worktree entries** across two
registered projects — every one flagged `prunable gitdir file points to non-existent
location`.

Today the only tools are `set-project remove <name>` (one at a time, by hand) and
`set-cleanup --older-than Nd` (worktree GC for merged changes). Nothing prunes the registry
itself, so this grows monotonically.

## What Changes

- **New `set-project prune` command.** Default run deregisters only entries whose `path` is
  not an existing directory, and runs `git worktree prune` in each registered, existing
  project. This mode is *structurally incapable* of touching a project whose directory
  exists.
- **`--dry-run` reports without writing.** Zero writes, measured rather than asserted —
  following the `set-project init --dry-run` precedent of being honest about its own blast
  radius.
- **Archival instead of deletion for live directories.** Old E2E runs exist on disk, so they
  are never deregistered. `--archive-e2e-older-than <Nd>` marks them `archived: true` +
  `archivedAt` in the registry; the entry and everything on disk stay. Reversible.
  Restricted to projects under the framework's `e2e-runs/` root, because **age alone cannot
  separate them** — measured on a live registry: two ordinary development projects were 62
  days idle, exactly as old as the E2E runs to be archived. Location separates them; age does
  not.
- **`GET /api/projects` hides archived entries by default**, `?include_archived=true` returns
  them. The existing `DELETE /api/projects/{name}` is untouched.
- **A timestamped backup of `projects.json` is written before any mutation.**

**Not a breaking change**: entries without an `archived` field behave exactly as today.

## Capabilities

### New Capabilities
- `registry-prune`: deregistering registry entries whose directory is gone, pruning orphaned
  git worktree records, and archiving (never deleting) registry entries whose directory
  still exists — under a loss-free guarantee that is enforced by tests, not by documentation.

### Modified Capabilities
- `manager-api`: `GET /api/projects` gains archived-entry filtering and an
  `include_archived` query parameter.

## Impact

- **New**: `lib/set_orch/registry_prune.py` — the whole mechanism, so the CLI and the API
  share one implementation.
- `lib/set_orch/api/helpers.py` — `PROJECTS_FILE` (:23), `_load_projects()` (:45),
  `_save_projects()` (:70); `_save_projects` gains the pre-write backup.
- `lib/set_orch/api/projects.py` — `list_projects()` (:24) filters archived entries.
- `bin/set-project` — new `prune` subcommand in the dispatch `case` (:1427) and `usage()`
  (:683).
- `web/src/hooks/useProjectOverview.ts`, `web/src/pages/Manager.tsx`, `web/src/lib/api.ts` —
  archived projects drop out of the overview.
- **Untouched by design**: no `rm`, no `shutil.rmtree`, no `git worktree remove`, no branch
  deletion, anywhere in the new code. `git worktree prune` is the sole git mutation, and it
  only ever discards administrative records for directories that are already gone — measured:
  all 10 orphans belong to `change/*` branches, whose commits survive the prune.

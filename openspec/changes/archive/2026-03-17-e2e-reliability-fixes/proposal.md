## Why

E2E MiniShop Run #17 (11/11 merged, 5h17m) required 11 manual merge interventions — all caused by the same verify retry exhaustion bug (node_modules dirty files). CraftBrew Run #2 was interrupted after 2/15 changes when `wt-merge` deleted the `orchestration-state.json` file during its untracked-file cleanup. Additionally, worktrees that receive a post-merge sync don't get dependency reinstallation, causing build failures in later phases.

## What Changes

- **Close flock fd before spawning orchestrator child** — sentinel's fd 9 (flock) is inherited by the orchestrator and all its children; if sentinel dies but orchestrator lives, the flock is never released and next sentinel start fails with "Failed to acquire lock"
- **Reinstall dependencies after worktree sync** — `sync_worktree_with_main()` merges master into running worktrees but doesn't run `pnpm install` when `package.json` or lockfiles change, causing missing module errors
- **Update bug index status** — Bugs #37, #38, #24, #9 have been fixed in prior commits but README status entries still show "open" or "recurring"

## Capabilities

### New Capabilities
- `worktree-deps-sync`: Automatic dependency reinstallation when worktree sync detects lockfile or package.json changes

### Modified Capabilities
- `stale-lock-recovery`: Close inherited flock fd in child processes so sentinel lock is always released on sentinel exit

## Impact

- `bin/wt-sentinel` — single line: add `9>&-` to child spawn (L455)
- `lib/wt_orch/dispatcher.py` — `sync_worktree_with_main()`: detect lockfile/package.json changes in merge diff, run `pnpm install` if changed
- `tests/e2e/minishop/README.md` — bug index status updates
- `tests/e2e/craftbrew/README.md` — bug index status updates

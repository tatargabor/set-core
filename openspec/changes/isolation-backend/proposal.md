# Proposal: Isolation Backend

## Why

The orchestration engine is hardcoded to `git worktree` for change isolation. This prevents using set-core in environments where git worktrees are problematic (shared `.git` dir causes `index.lock` conflicts, worktree pruning issues) or where a simpler branch-clone approach would suffice. Introducing an abstraction layer lets the same orchestration logic work with different isolation strategies — starting with the existing worktree approach and a new branch-clone backend.

## What Changes

- **New**: `IsolationBackend` abstract interface in `lib/set_orch/isolation.py` with `create()`, `remove()`, `list_active()`, `sync_with_main()` methods
- **New**: `WorktreeBackend` implementation wrapping existing `git worktree add/remove/list` calls
- **New**: `BranchCloneBackend` implementation using `git clone --branch` for full isolation
- **Modified**: ~15 direct `git worktree` call sites in dispatcher, merger, planner, api, milestone, and CLI scripts replaced with backend method calls
- **Modified**: `orchestration.yaml` gains `execution.isolation` config key (`worktree` | `branch-clone`)
- CLI command names (`wt-new`, `wt-close`, `wt-merge`) and state field names (`worktree_path`) remain unchanged

## Capabilities

### New Capabilities
- `isolation-backend` — Abstract isolation layer with pluggable backends for change workspace creation

### Modified Capabilities
- (none — existing specs describe change lifecycle at a higher level than git operations)

## Impact

- **Core orchestration**: dispatcher.py, merger.py, planner.py, api.py, milestone.py — all `git worktree` calls routed through backend
- **CLI scripts**: `bin/wt-new`, `bin/wt-close` — delegate to backend instead of direct git commands
- **Config**: new `execution.isolation` key in orchestration.yaml
- **State schema**: no change — `worktree_path` field stays as-is (it's a path, not a git concept)
- **GUI/MCP/skills**: no change — they operate on paths, not git internals
- **Tests**: new unit tests for both backends; existing E2E tests work unchanged (default backend = worktree)

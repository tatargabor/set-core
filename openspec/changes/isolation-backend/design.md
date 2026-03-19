# Design: Isolation Backend

## Context

Currently, ~15 direct `git worktree` calls are scattered across dispatcher.py, merger.py, planner.py, api.py, milestone.py, bin/wt-new, and bin/wt-close. These handle four operations: create, remove, list, and sync-with-main. The rest of the codebase (~200+ references to `worktree_path`) operates on paths and is backend-agnostic already.

The branch-clone approach uses `git clone --branch` to create fully independent repository copies. This eliminates shared `.git` directory issues (index.lock conflicts, worktree pruning problems) at the cost of more disk space.

## Goals / Non-Goals

**Goals:**
- Extract a clean interface from existing git worktree operations
- Add branch-clone as an alternative backend
- Make the backend configurable per orchestration run
- Zero behavior change for existing users (worktree remains default)

**Non-Goals:**
- Renaming any CLI commands, state fields, or user-facing terminology
- Supporting non-git VCS
- Optimizing clone disk usage (shallow clones, etc.) — can be added later

## Decisions

### D1: Single Python module for all backends

**Decision:** Create `lib/set_orch/isolation.py` containing the ABC and both implementations.

**Why over separate files:** The interface is small (4 methods). Both backends are ~50-80 lines each. A single module keeps imports simple and avoids over-fragmentation.

**Alternative considered:** `isolation/` package with `base.py`, `worktree.py`, `clone.py` — rejected as premature for 2 backends totaling ~200 lines.

### D2: Backend resolved at orchestrator startup

**Decision:** Read `execution.isolation` from orchestration.yaml once at startup, instantiate the backend, and pass it through the call chain.

**Why:** Avoids reading config at every call site. The backend is immutable for the duration of an orchestration run.

**Resolution chain:**
```
orchestration.yaml → config.get_isolation_backend() → IsolationBackend instance
```

### D3: Bash CLI scripts call Python backend

**Decision:** `wt-new` and `wt-close` call a thin Python entry point (`set-orch-core isolation create/remove`) instead of `git worktree` directly.

**Why:** The Python backend is the single source of truth. Duplicating logic in bash defeats the abstraction.

**Alternative considered:** Rewrite wt-new/wt-close in Python — rejected as too large a change for this scope. The bash scripts remain as wrappers.

### D4: BranchClone merge-back uses source repo as remote

**Decision:** The clone's `origin` remote already points to the source repo (since we `git clone <local_path>`). Merge-back works by pushing from the clone to origin, then merging in the source repo.

```
Source repo ←── git push (from clone) ←── Clone dir
     │                                       │
     └── origin remote ─────────────────────┘
```

**Why:** This matches how worktree merges work conceptually — the branch exists in the same repo. The clone just adds directory isolation.

### D5: Bootstrap operations stay in bash

**Decision:** The bootstrap steps in wt-new (env file copy, dependency install, hook deploy, editor config) remain in bash and run after the Python backend creates the directory. They are backend-agnostic — they operate on a path, not on git internals.

## Risks / Trade-offs

- **[Risk] Branch-clone uses more disk** → Mitigation: document this in config. For large repos, worktree backend remains recommended.
- **[Risk] Clone sync is slower than worktree sync** → Mitigation: `--single-branch` reduces fetch scope. Can add `--depth` later if needed.
- **[Risk] Two code paths to maintain** → Mitigation: shared test suite validates both backends produce identical outcomes.
- **[Risk] Bash→Python bridge adds complexity to wt-new/wt-close** → Mitigation: the bridge is a single subprocess call, and the Python layer is already used elsewhere (profile bootstrap).

## Open Questions

- Should `BranchCloneBackend.sync_with_main()` use merge or rebase? Current worktree sync uses merge. Start with merge for consistency.

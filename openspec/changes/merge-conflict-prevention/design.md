# Design: Merge Conflict Prevention

## Architecture

Three independent layers, each providing defense-in-depth:

```
git merge source_branch
  │
  ├─ Layer 1: .gitattributes merge=ours
  │  (lockfiles, .claude/**, *.tsbuildinfo → silently keep ours)
  │  → conflict NEVER appears for these files
  │
  ├─ Layer 2: wt-merge auto_resolve_generated_files(partial=true)
  │  (fallback when gitattributes not configured)
  │  → checkout --ours + regenerate lockfile
  │  → LLM only sees app code conflicts
  │
  └─ Layer 3: engine serialization
     (merge queue drained before dispatch)
     → no archive race, worktrees always have latest main
```

## D1: Generated File Pattern Coverage

**Decision:** Expand `GENERATED_FILE_PATTERNS` in `wt-merge` and `_CORE_GENERATED_FILE_PATTERNS` in `dispatcher.py` to cover all observed conflict sources.

Current patterns miss: `coverage/**`, `node_modules/**`.

Add to wt-merge `GENERATED_FILE_PATTERNS`:
- `coverage/**` (test coverage output)
- `node_modules/**` (pnpm symlinks — Bug #37 root cause)

These are already in `_AUTO_RESOLVE_PREFIXES` in dispatcher.py but not in wt-merge's bash array.

## D2: Engine Merge-Before-Dispatch Serialization

**Decision:** In the engine loop, check merge queue before dispatching. If queue is non-empty, drain it completely, then dispatch.

```python
# engine.py loop tick — BEFORE:
_dispatch_ready_safe(state_file, d, event_bus)   # may race with merge
_retry_merge_queue_safe(state_file, event_bus)    # may miss archive

# AFTER:
state = load_state(state_file)
if state.merge_queue:
    _drain_merge_then_dispatch(state_file, d, event_bus)
else:
    _dispatch_ready_safe(state_file, d, event_bus)
```

The `_drain_merge_then_dispatch` helper:
1. Calls `execute_merge_queue()` (existing) — drains all pending merges
2. Calls `_sync_running_worktrees()` post-merge (existing — already in merger.py)
3. Then calls `_dispatch_ready_safe()` — new worktrees created AFTER archive commits

This eliminates Bug #38 (archive race) without changing merger.py.

## D3: Gitattributes in bootstrap_worktree()

**Decision:** When `bootstrap_worktree()` creates a new worktree, configure `merge.ours.driver` in the worktree's local git config. The `.gitattributes` file is already in the repo (committed by scaffold), but `git config merge.ours.driver true` is per-repo and needs to be set in each worktree.

Actually — worktrees share the main repo's git config. So `git config merge.ours.driver true` only needs to run once in the main project, which the scaffold already does. No change needed in bootstrap_worktree().

**Revised decision:** No bootstrap_worktree() change. The scaffold `git config` covers all worktrees.

## D4: Post-Merge Hook — Explicitly Rejected

Experimentally validated that post-merge hooks leave dirty working tree state (49 node_modules symlink changes), which blocks subsequent merges. Lockfile regeneration must happen through `wt-merge`'s `regenerate_lockfile()` and `merger.py`'s `_post_merge_deps_install()`.

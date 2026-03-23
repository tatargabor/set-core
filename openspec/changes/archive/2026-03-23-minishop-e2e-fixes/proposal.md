# Proposal: minishop-e2e-fixes

## Problem

During minishop-run1 E2E test, several framework bugs were discovered that caused delays, stuck states, and manual interventions. These are all in the orchestration engine and merger, not in the consumer project.

## Issues Found

### 1. Stale orchestrator.lock (Bug #33)
- `orchestrator.lock` uses `fcntl.flock` but the lock file persists after process death
- Sentinel restart hits "Another orchestrator already running" and enters crash loop
- Required manual lock cleanup multiple times during the run
- **Root cause**: The bash `cmd_start` wrapper exec's to Python, but the lock fd inheritance through exec is unreliable

### 2. verify_retries counter resets on stall recovery
- admin-dashboard had 2 verify retries (test fail + review fail) but state showed `r:0`
- The `resume_change()` path doesn't preserve the retry counter
- **Impact**: Inaccurate E2E reporting, can't track actual retry rates

### 3. merge_change() ff-merge failure despite valid state
- shopping-cart passed all integration gates but `merge_change()` still failed
- Manual `git merge --ff-only` succeeded immediately
- **Root cause**: Likely a race condition or stale state in the merge flow — needs investigation

### 4. Stale worktrees from bad restarts (-2, -3 suffixes)
- Each restart that fails creates orphaned worktrees with incrementing suffixes
- These consume disk and confuse the worktree list
- The sentinel should clean up stale worktrees before dispatching

## Scope

All changes in `lib/set_orch/` (engine.py, merger.py, dispatcher.py) and `bin/set-sentinel`.

## Non-goals

- No consumer project changes
- No new features — only reliability fixes

# Proposal: merge-on-branch

## Why

The current merge pipeline runs gate checks (build, test, review) on the feature branch without main integrated, then merges into main. This creates a dangerous gap: gates pass on the branch but fail after merge because main has changed. When this happens, main breaks, the `build_broken_on_main` flag halts all dispatch, and `smoke_fix_scoped` runs directly on main trying to fix the damage. Post-merge build failures require manual intervention, and worktree cleanup after merge makes recovery impossible because the agent's context is gone.

This is the single largest source of orchestration downtime and wasted tokens.

## What Changes

- **Invert the merge direction**: instead of merging branch INTO main after gates pass, merge main INTO the branch BEFORE gates run. Gates then verify the integrated state, ensuring what passes on branch will also pass on main.
- **Fast-forward-only merge to main**: once gates pass on the integrated branch, advance main via `--ff-only`. This guarantees main only ever moves forward to a tested commit.
- **Re-integration retry loop**: if ff-only fails because main advanced while gates ran, re-integrate main into branch and re-run gates. Repeat until ff succeeds or a retry limit is hit.
- **Remove post-merge recovery machinery**: `smoke_fix_scoped` on main, `build_broken_on_main` flag, dispatch halting, and post-merge build checks are all eliminated — they exist only to handle a problem this change prevents.
- **New "integrating" status**: track when a change is in the main-integration phase (between implementation completion and gate execution).

## Capabilities

### New Capabilities
- `main-integration` — merge main into feature branch before gates, handle conflicts on branch
- `ff-only-merge` — fast-forward-only merge to advance main, with retry loop on race

### Modified Capabilities
- (none — existing specs are not changed at the requirement level)

## Impact

- **verifier.py**: new `_integrate_main_into_branch()` step before gate pipeline in `handle_change_done()`
- **merger.py**: `merge_change()` simplified to ff-only, removal of `smoke_fix_scoped` dependency, removal of `build_broken_on_main` logic, removal of post-merge build check
- **engine.py**: removal of `_retry_broken_main_build_safe()`, removal of `build_broken_on_main` dispatch guard, handle re-integrate retry when ff fails
- **bin/set-merge**: add `--ff-only` mode for orchestrator use
- **state.py**: new "integrating" status value
- **Breaking**: `smoke_fix_scoped` is removed from the post-merge pipeline. Projects relying on post-merge smoke fix behavior will need to configure pre-merge smoke via gate profiles instead.

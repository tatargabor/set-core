# Proposal: Craftbrew Run #11 Fixes

## Why

Craftbrew Run #11 exposed 4 framework bugs that caused 50+ wasted merge attempts, 3 stalled changes requiring manual intervention, and an orchestrator that got stuck in an infinite loop. The run achieved 6/11 merged but 2 changes were permanently merge-blocked due to infinite retry loops (31x and 19x MERGE_ATTEMPT respectively). These are pipeline-level issues that affect every E2E run.

## What Changes

- **Fix infinite merge retry loop** — `execute_merge_queue()` never checks `merge_retry_count`, allowing unlimited retries. The counter implemented in `retry_merge_queue()` is bypassed by the monitor's "orphaned done" re-add logic.
- **Fix done→stalled race condition** — Changes that complete (loop-state=done) get marked "stalled" by the dead agent detector before the merge pipeline processes them. `_poll_suspended_changes()` doesn't handle "stalled" status, so they're stuck forever.
- **Add web template .gitignore** — The nextjs template has no .gitignore file. `playwright-report/`, `test-results/`, and `.claude/` cache files are tracked, causing dirty worktrees that block every integration merge.
- **Fix set-merge ff-only branch resolution** — `set-merge --ff-only` fails because it uses the worktree branch name (`change/foo`) which doesn't resolve in the main repo context. Manual `git merge --ff-only` works fine.

## Capabilities

### New Capabilities
- `web-template-gitignore` — Web template ships a proper .gitignore for generated/test artifacts

### Modified Capabilities
- `merge-retry-counter` — Counter check enforced in execute_merge_queue, not just retry_merge_queue
- `stalled-change-recovery` — _poll_suspended_changes handles "stalled" status with loop-state done check
- `merge-branch-resolution` — set-merge resolves worktree branch refs correctly for ff-only merges

## Impact

- `lib/set_orch/merger.py` — retry counter check in execute_merge_queue
- `lib/set_orch/engine.py` — stalled recovery in _poll_suspended_changes
- `bin/set-merge` — branch resolution fix for ff-only path
- `modules/web/set_project_web/templates/nextjs/` — new .gitignore + manifest update

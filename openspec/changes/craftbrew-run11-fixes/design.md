# Design: Craftbrew Run #11 Fixes

## D1: Merge Retry Counter in execute_merge_queue

**Decision:** Add retry counter check at the TOP of the `execute_merge_queue()` loop, before `_integrate_for_merge()`.

```python
# merger.py execute_merge_queue(), inside the for loop:
retry_count = change.extras.get("merge_retry_count", 0)
if retry_count >= MAX_MERGE_RETRIES:
    logger.warning("Merge retry limit reached for %s (%d/%d)", name, retry_count, MAX_MERGE_RETRIES)
    update_change_field(state_file, name, "status", "integration-failed")
    _remove_from_merge_queue(state_file, name)
    continue
```

**Counter increment stays ONLY in `retry_merge_queue()`** — this is the single point of increment. `execute_merge_queue()` only CHECKS the counter, never increments. This avoids double-counting: `retry_merge_queue()` finds merge-blocked → increments → re-adds → `execute_merge_queue()` processes. If we also incremented in `execute_merge_queue()`, each failure would count as 2.

Unify `MAX_MERGE_RETRIES` to a single global constant = 3 (currently there's a local = 3 in `retry_merge_queue()` and a global = 5 at module level).

Additionally, in `_poll_suspended_changes()`, check retry count before re-adding orphaned "done" changes to the merge queue. Emit `CHANGE_INTEGRATION_FAILED` event when the limit is reached for dashboard/sentinel visibility.

## D2: Stalled Change Recovery

**Decision:** Add "stalled" to the status filter in `_poll_suspended_changes()` and check loop-state.json for done status.

After the existing "done" handling block (engine.py ~line 775), add a "stalled" handling block:
- Read loop-state.json from the change's worktree
- If status is "done": set change status to "done", add to merge queue
- If status is NOT "done": leave stalled (genuine stall, needs manual intervention)

This is the minimal fix — no changes to the dead agent detector timing.

## D3: Set-Merge FF-Only Branch Resolution

**Decision:** Remove `2>/dev/null` from the `git merge --ff-only` call to expose the actual error, and add branch existence verification before attempting the merge.

In `bin/set-merge` ff-only section:
1. Before `git merge --ff-only`, verify the source branch exists: `git show-ref --verify "refs/heads/$source_branch"`
2. If it doesn't exist, try fetching from worktree: the branch should be shared (git worktrees share refs), so this indicates a corrupted worktree state
3. Remove `2>/dev/null` from the merge command to capture the actual error
4. Add diagnostic logging: merge-base, HEAD, source HEAD

## D4: Web Template Gitignore

**Decision:** Create `.gitignore` in the nextjs template and add it to `manifest.yaml`.

The .gitignore covers:
- Standard Next.js: `.next/`, `out/`, `node_modules/`
- Prisma: `*.db`, `*.db-journal`, `prisma/generated/`
- Test output: `playwright-report/`, `test-results/`, `coverage/`
- Build: `tsconfig.tsbuildinfo`, `next-env.d.ts`
- Claude CLI: `.claude/logs/`, `.claude/digest-last-response.txt`
- Environment: `.env`, `.env.*` (except `.env.example`)
- OS: `.DS_Store`, `Thumbs.db`

The template .gitignore is additive — projects can extend it. `set-project init` deploys it via the manifest.

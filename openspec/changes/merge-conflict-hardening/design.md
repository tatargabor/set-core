## Context

The orchestrator merges completed changes via `merge_change()` → `wt-merge --no-push --llm-resolve`. When `wt-merge` fails, the orchestrator tries agent-assisted rebase (once), then falls back to `retry_merge_queue` which retries up to 5 times with 15s delays. In a 6-change live batch, all 4 non-trivial merges ended up merge-blocked and required manual intervention.

Key code paths:
- `merge_change()` (line ~3631): calls `wt-merge`, on failure triggers agent rebase or sets merge-blocked
- `_try_merge()` (line ~3764): retry logic with `git merge origin/main` in worktree before each attempt
- `retry_merge_queue()` (line ~3798): iterates queue + finds orphaned merge-blocked changes
- Monitor loop "all done" check: counts changes with status not in running/pending/verifying

## Goals / Non-Goals

**Goals:**
- Agent rebase succeeds on trivial conflicts (generated files + union-type additions)
- Merge retries stop early when the conflict is unchanged
- Merge-blocked changes are not falsely counted as "complete"
- Log noise from merge retries is reduced
- New dependencies from merged branches are installed on main before subsequent builds

**Non-Goals:**
- Changing wt-merge's LLM resolution strategy (that's a separate concern)
- Handling complex multi-file semantic conflicts (those legitimately need human review)
- Changing the merge policy options (eager/checkpoint/manual)

## Decisions

### 1. Agent rebase prompt must include done-signal instruction
**Decision**: Add "After committing the merge, create a file `.claude/merge-done` to signal completion" or equivalent done signaling to the rebase prompt. The agent runs with `--done manual --max 2`, so it needs an explicit way to tell the loop it's done.

**Rationale**: Currently the agent resolves the conflict but the loop doesn't know it's done, so it runs 2 iterations and then gets marked stalled. The simpler fix: change done-criteria to `tasks` or detect the merge commit automatically in `handle_change_done()`.

**Chosen approach**: After the agent rebase loop ends, check if the branch now merges cleanly into main (fast-forward or auto-merge). If it does, proceed to merge. If it doesn't, mark merge-blocked. This avoids needing the agent to signal anything — we just check the result.

### 2. Conflict fingerprint for smart retry
**Decision**: Before each merge retry, compute a fingerprint of the conflict (sorted list of conflicted file paths). If the fingerprint matches the previous attempt's fingerprint, stop retrying immediately.

**Alternative considered**: Hash the conflict markers content. Rejected as over-engineering — if the same files conflict, the same content will conflict (since `git merge origin/main` in worktree already pulls latest).

### 3. Merge-blocked exclusion from all-done
**Decision**: The "all done" check in monitor_loop should explicitly exclude `merge-blocked` and `failed` statuses. Only `merged` and `done` count as complete.

**Rationale**: Currently `merge-blocked` falls through the status checks and gets counted as complete, which triggers a premature auto-replan cycle.

### 4. Log level demotion for retry attempts
**Decision**: First merge conflict for a change emits `log_error`. Subsequent retry attempts for the same change emit `log_info` with the attempt counter. Only the final failure (exhausted retries) emits `log_error` again.

**Rationale**: 5 retries × 6 changes = 30 ERROR lines for what is often a single `.claude/reflection.md` conflict. This floods desktop notifications and log tails.

### 5. Post-merge dependency install
**Decision**: After a successful merge in `merge_change()`, detect if `package.json` changed in the merged diff. If so, run the project's package manager install command (`pnpm install`, `npm install`, or `yarn install` — auto-detected from lockfile presence). This runs synchronously before the next verify gate or merge.

**Rationale**: Each worktree has its own `node_modules` populated by `wt-new`'s bootstrap. But main's `node_modules` is stale — it doesn't get new packages added by the merged branch. When the next change's verify gate runs `pnpm run build` on main (for the base build check), or when the user runs the dev server, they hit `Module not found` errors for packages that exist only in the merged branch's worktree.

**Alternative considered**: Always run install after every merge. Rejected — `pnpm install` takes 5-15s and most merges don't change dependencies. Checking `package.json` diff is cheap.

## Risks / Trade-offs

- **Risk**: Post-rebase merge check might have false positives if worktree state is stale → **Mitigation**: Do `git fetch origin main` before the test merge
- **Risk**: Conflict fingerprint is too coarse (same files but different content) → **Mitigation**: Acceptable — if the same files conflict after pulling latest main, the content hasn't changed either
- **Trade-off**: Reducing log_error to log_info for retries makes it harder to find merge issues in logs → **Mitigation**: The first and final attempt still use log_error, and retry count is always visible
- **Risk**: Post-merge `pnpm install` fails (network, corrupted lockfile) → **Mitigation**: Log warning but don't block — the merge itself succeeded, install failure is recoverable

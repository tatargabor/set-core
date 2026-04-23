# Proposal: fix-merge-worktree-collision

## Why

When a change is reset to `pending` mid-run (circuit-breaker auto-retry, stalled-change recovery, or manual reset), the on-disk worktree directory and `change/<name>` branch are left intact while the in-memory state forgets them. The dispatcher's next cycle detects the branch collision, bumps the worktree name to `<name>-2`, and both worktrees then coexist — one orphaned, one live. The merger's subsequent `set-merge <name>` call rediscovers worktrees by regex and returns the **first** match (git-worktree-list order), which is typically the stale unsuffixed one. Fast-forward merge fails on a stale merge-base.

The merger already has local caps (`MAX_MERGE_RETRIES=3` per cycle, `MAX_TOTAL_MERGE_ATTEMPTS=10` across cycles) that eventually mark the change `merge-blocked` → `integration-failed`. But `integration-failed` is a silent terminal state — the operator only sees it by reading logs, and the parent change has no automatic unblocking path. Worse, these caps were not yet in place when the originating incident occurred: **282 merge attempts over 5 hours** blocking 22 pending changes. Even with today's caps the worst case is still ~10 wasted attempts per stall, each consuming minutes of dispatch+gate+merge time, and the collision keeps re-seeding itself on every operator-triggered retry.

This change closes three separate gaps:
1. **Seed removal** — every reset-to-pending path must also remove the change's on-disk worktree + branch, so re-dispatch cannot spawn a `-N` collision suffix.
2. **Deterministic discovery** — when the caller has the authoritative worktree path, pass it explicitly instead of rediscovering by regex; harden the regex scanners for the interactive cases that cannot know the path.
3. **Visible escalation** — replace the silent `integration-failed` terminal with a `failed:merge_stalled` escalation through the existing fix-iss pipeline, so the parent unblocks automatically once the root cause is addressed and operators see the stall on the Issues tab instead of only in logs.

## What Changes

- **NEW**: `lib/set_orch/change_cleanup.py` — shared idempotent helper `cleanup_change_artifacts(change_name, project_path)` that removes the worktree directory and deletes the `change/<name>` branch, tolerant of missing artifacts so repeated calls are no-ops.
- **MODIFIED**: `lib/set_orch/issues/manager.py` — circuit-breaker parent auto-retry (`_retry_parent_after_resolved`) invokes `cleanup_change_artifacts` before `reset_change_to_pending`, so the next dispatch starts from a clean slate.
- **MODIFIED**: `lib/set_orch/recovery.py` — plan-execute path uses the shared helper instead of bespoke inline worktree removal; reset helper documents that callers must purge artifacts separately or via the helper.
- **MODIFIED**: `bin/set-merge` — new `--worktree <path>` flag. When given, the script trusts the explicit path and skips `find_existing_worktree`. Callers that already know the authoritative path (e.g. the merger reading `change.worktree_path`) pass it through; interactive callers keep the discovery fallback.
- **MODIFIED**: `lib/set_orch/merger.py` — `merge_change` passes `change.worktree_path` via `--worktree` to `set-merge`. Adds a persistent merge-stall circuit-breaker: `merge_stall_attempts` counter in `change.extras`, at threshold (default 20) the change transitions to `failed:merge_stalled` and escalates to `fix-iss` via the existing issue pipeline.
- **MODIFIED**: `bin/set-common.sh` — `find_existing_worktree` collects all candidate matches, prefers the highest numeric suffix, and logs a WARNING when multiple matches exist with divergent HEADs. Defensive for interactive CLI invocations that cannot know the authoritative path.
- **MODIFIED**: `lib/set_orch/dispatcher.py` — Python-side `_find_existing_worktree` replaces substring-match (`change_name in line`) with exact basename match against both naming conventions (`{project}-{name}` and `{project}-wt-{name}`).

## Capabilities

### New Capabilities
- `change-artifact-cleanup` — Single source of truth for removing a change's on-disk artifacts (worktree directory, git branch). Idempotent, callable from any reset/recovery path.

### Modified Capabilities
- `merger` — Adds explicit worktree-path passthrough and persistent merge-stall escalation. Merge failures can no longer trap the orchestrator in an unbounded retry loop.
- `merge-worktree` — `set-merge` accepts an authoritative `--worktree` path; worktree-discovery regex is hardened against multiple-match ambiguity.
- `worktree-tools` — `find_existing_worktree` now has defined behavior under ambiguity (prefer highest suffix, WARN), and the Python-side finder drops substring matching.
- `issue-state-machine` — Circuit-breaker parent retry guarantees artifact cleanup before reset so re-dispatch cannot spawn collision-suffixed duplicates.
- `dispatch-recovery` — Reset-to-pending paths share a common artifact-cleanup contract.

## Impact

- New module: `lib/set_orch/change_cleanup.py`
- Modified: `lib/set_orch/merger.py`, `lib/set_orch/recovery.py`, `lib/set_orch/issues/manager.py`, `lib/set_orch/dispatcher.py`, `bin/set-merge`, `bin/set-common.sh`
- New persistent state field: `change.extras["merge_stall_attempts"]` (integer counter). Backwards-compatible — missing key treated as 0.
- New terminal status: `failed:merge_stalled`. Handled by existing `failed:*` prefix-match in dispatcher/engine halt logic.
- No schema changes to `orchestration-state.json` beyond the additive `extras` counter.
- No new dependencies.

**Out of scope** (potential future change): lineage-namespaced branches and worktree directories (`change/<lineage_slug>/<name>`, `<project>-<lineage_slug>-wt-<name>`) to prevent collision when two spec lineages produce identically-named changes. Pursue only if spec-switch cross-lineage collisions become observable.

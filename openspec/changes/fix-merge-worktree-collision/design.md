## Context

A change's on-disk representation consists of two artifacts: the worktree directory (conventionally `{project}-wt-{name}` in bash-created paths, `{project}-{name}` in direct-`git worktree add` Python paths) and the git branch `change/{name}`. The in-memory representation is `Change.worktree_path` plus the derived branch name. There are currently three code paths that "forget" the in-memory record without removing the on-disk artifacts:

1. `recovery.reset_change_to_pending(ch)` — mutates the Change dataclass only.
2. `IssueManager._retry_parent_after_resolved` — calls `reset_change_to_pending` with no FS cleanup.
3. Manual operator interventions (ad-hoc `openspec delete`, state edits).

The full recovery CLI (`set-recovery`) is the only caller that pairs state reset with FS cleanup, and it does so via a bespoke `worktrees_to_remove` list computed at plan time.

The dispatcher, when it later sees a dangling branch or directory, treats the collision as a fresh-dispatch ambiguity and bumps the name to `-2`. This creates two parallel records for the same logical change: one live, one orphan. Both match `find_existing_worktree` (bash regex `^{repo}-wt-{name}(-[0-9]+)?$`) and the Python `_find_existing_worktree` (substring `change_name in line`). Neither scanner tolerates ambiguity; both return the first match, which is order-dependent on git's worktree creation timeline.

When the merger calls `set-merge <name>`, the scanner picks the wrong worktree, the FF merge fails on a stale merge-base, and the engine retries indefinitely because there is no persistent stall counter. The tightest observed loop produced 282 merge attempts in 5 hours against a single change, consuming the run's remaining CPU and token budget while blocking 22 pending changes behind the queue.

## Goals / Non-Goals

**Goals:**

- Eliminate the seed of the collision: every reset-to-pending path either cleans FS artifacts itself or delegates to a shared helper that does.
- Make worktree discovery deterministic when the caller has the authoritative path. Passing the path explicitly through the merge pipeline removes the need to rediscover.
- Harden the two discovery fallbacks for interactive callers (they cannot know the authoritative path) so ambiguity is detected and logged rather than resolved silently-wrong.
- Put an upper bound on merge retries so any future merge bug cannot consume unbounded CPU. Escalation through the existing `fix-iss` pipeline turns a silent stall into a visible, actionable issue.

**Non-Goals:**

- Renaming existing branches, worktrees, or state entries created before this change. The new flow is additive and backwards-compatible.
- Lineage-namespaced branches or worktree dirs (`change/{lineage_slug}/{name}`). Decision recorded as deferred: the observed failure mode is within a single lineage, not across lineages. Revisit only if spec-switch collisions become observable in practice.
- Unifying the bash and Python worktree-path conventions (`-wt-` infix vs. none). Both conventions persist for backwards compatibility; the discovery scanners will accept both.
- Reworking `set-recovery`'s plan-execute path beyond refactoring to use the shared helper. The full rollback flow is out of scope for this change.

## Decisions

### D1: Shared helper vs. inline cleanup in each caller

**Decision:** Extract `cleanup_change_artifacts(change_name, project_path)` into a new module `lib/set_orch/change_cleanup.py`. Call it from every reset path.

**Alternative considered:** Push cleanup into `reset_change_to_pending(ch, project_path=None)`. Simpler, one fewer module. Rejected because `reset_change_to_pending` is used in two very different contexts: (a) recovery CLI where the caller has already planned and removed worktrees separately, and (b) mid-run circuit-breaker where no pre-planning exists. Adding an optional FS-cleanup arg to a state-mutator confuses the contract. A standalone helper is clearer and easier to unit-test in isolation.

**Why shared helper wins:**

- Unit-testable against a temporary git repo without wiring up a Change dataclass.
- Reusable from bash via a thin CLI wrapper if needed (future work).
- Single place to maintain idempotency guards and logging.

### D2: Idempotency contract

**Decision:** `cleanup_change_artifacts` is a no-op when the worktree or branch does not exist. Specifically:

1. If the canonical worktree path (`{project}-wt-{name}` AND `{project}-{name}`) does not exist on disk, skip `git worktree remove`.
2. If the worktree directory exists but is not a registered git worktree (detected via `git worktree list --porcelain` parse), skip `git worktree remove` and `rm -rf` the directory.
3. Run `git worktree prune` unconditionally to tidy `.git/worktrees/` stale entries.
4. If `change/{name}` branch exists, run `git branch -D`. Ignore "not found" exit code.
5. All operations log at INFO on success, WARN on unexpected failure.

Rationale: repeated calls (e.g., recovery's plan-execute already removes worktrees, then calls `reset_change_to_pending` which now also calls cleanup) must not double-fail.

### D3: Explicit worktree-path passthrough in `set-merge`

**Decision:** Add `--worktree <path>` flag to `bin/set-merge`. When present, skip `find_existing_worktree`; use the path directly after validating it is a directory AND a registered git worktree. The merger (`lib/set_orch/merger.py`) passes `change.worktree_path` via this flag.

**Alternative considered:** Teach `find_existing_worktree` to consult `state.json` first. Rejected because `set-merge` is also a user-facing CLI with no guaranteed state context; coupling it to the orchestrator's state file breaks isolation. Passing the path explicitly is a one-line merger change that the user-facing CLI accepts but does not require.

### D4: Fallback discovery under ambiguity

**Decision:** `find_existing_worktree` (bash) collects all candidate matches. Resolution rules:

1. If exactly one match: return it.
2. If multiple matches and state has a value for this change's `worktree_path` that equals one of the matches: return that one.
3. Otherwise, prefer the match with the highest numeric suffix (`{name}-3` > `{name}-2` > unsuffixed).
4. Always emit a WARN log listing all candidates when ambiguity is detected, so operators can investigate.

Python `_find_existing_worktree` (`lib/set_orch/dispatcher.py`) replaces its substring check with an exact basename match against `{project_name}-{name}` AND `{project_name}-wt-{name}`. Same ambiguity rules as bash.

Rationale for "highest suffix wins": the highest suffix is the most recently created, which is almost always the one the dispatcher's last unique-name resolution produced. Stale unsuffixed leftovers are by definition older.

### D5: Persistent merge-stall circuit-breaker

**Decision:** Track `merge_stall_attempts` in `change.extras` (additive, backwards-compatible). Increment on each `merge_change` call that ends in a FF failure, next to the existing `ff_retry_count` (per-cycle) and `total_merge_attempts` (cross-cycle) counters. The new counter is semantically distinct: it counts stalls that specifically indicate the merge is not making progress — i.e. FF failures. At threshold (default 6, configurable via `state.extras["directives"]["merge_stall_threshold"]`), transition to `failed:merge_stalled` and escalate via the existing `escalate_change_to_fix_iss` function.

**Calling convention (verified against `lib/set_orch/issues/manager.py:710`):** the function takes `state_file`, `change_name`, `stop_gate`, `escalation_reason`, `findings`, `event_bus` as keyword arguments. It does NOT take `source` or `affected_change` directly — both are derived internally (`source` becomes `circuit-breaker:{escalation_reason}`, `affected_change` is set from `change_name`). The call site looks like:

```python
escalate_change_to_fix_iss(
    state_file=state_file,
    change_name=change_name,
    stop_gate="merge",
    escalation_reason="merge_stalled",
    event_bus=event_bus,
)
```

**Threshold rationale:** `MAX_MERGE_RETRIES=3` and `MAX_TOTAL_MERGE_ATTEMPTS=10` already cap the raw attempt count. The new stall counter triggers EARLIER — at 6 consecutive FF failures that came through the stall path (same root cause, not fresh integration conflicts). This surfaces the issue on the Issues tab before the total-attempts cap turns the parent into silent `integration-failed`. A threshold of 6 is empirically above transient blips but tight enough to catch the failure within ~3 minutes given 30s-per-attempt.

**Why escalate through fix-iss:** The pipeline already handles token-runaway and retry-budget-exhausted cases. Reusing it gives users a consistent UI surface (the Issues tab) and ensures the parent change is eventually unfailed via the existing `_retry_parent_after_resolved` hook, which matches on `issue.source.startswith("circuit-breaker:")` — no additional whitelisting is needed because `merge_stalled` produces the expected `circuit-breaker:merge_stalled` source string.

### D6: Clean-up order in the auto-retry hook

**Decision:** In `IssueManager._retry_parent_after_resolved`, the order is:

1. `cleanup_change_artifacts(parent_name, project_path)` — disk first.
2. `reset_change_to_pending(ch)` — in-memory second, always runs even if cleanup had warnings.
3. Audit log + `logger.info`.

Rationale: disk cleanup first so the next dispatch cycle finds a clean filesystem and cannot spawn a `-N` collision. The state reset runs unconditionally because leaving the parent stuck in `failed:merge_stalled` defeats the purpose of the auto-retry. If cleanup warns about missing artifacts (benign), we still reset. If cleanup fails catastrophically (e.g., unexpected git error), the WARN is logged, an audit entry `parent_retry_cleanup_degraded` is recorded so operators can investigate, and the reset proceeds so at least the state machine moves forward — a half-reset state would produce a worse operator experience than a reset-with-degraded-cleanup.

## Risks / Trade-offs

- **[Risk] Cleanup races with a running dispatch** → Mitigation: cleanup is only called when the Change's status is `failed:*` (terminal) or during the circuit-breaker's reset-to-pending path. The dispatcher never dispatches a change whose status is `failed:*`, so there is no live agent to race with. Concurrent `set-recovery` is protected by the existing state lock.

- **[Risk] `git worktree remove --force` loses uncommitted work** → Mitigation: the affected change is, by definition, in `failed:*` or being reset. If the agent had uncommitted work worth preserving, it lost it at the failure boundary, not here. The operator has `set-recovery` to roll back if data recovery is needed; this change does not make that worse.

- **[Risk] Threshold-20 circuit-breaker fires on legitimate slow merges** → Mitigation: threshold is configurable via directives. A merge that takes > 20 attempts is almost certainly pathological given per-attempt costs (~30s). The escalation path does not destroy the change — it just surfaces an issue.

- **[Trade-off] Highest-suffix-wins fallback can be wrong** when a suffixed leftover exists but the live worktree is unsuffixed (inverse of the observed pathology). The WARN log makes the ambiguity visible. In the observed pathology, state-based disambiguation (rule 2 in D4) covers the primary case; suffix heuristic is only used when no state hint exists.

- **[Trade-off] `--worktree` flag adds a surface to `set-merge` that interactive users will not know about.** The help output documents it; the flag is optional; all existing invocations work unchanged.

## Migration Plan

1. **No data migration needed.** `merge_stall_attempts` is an additive key in `change.extras`; missing key treated as 0.
2. **No branch/worktree renaming.** Existing `-2`, `-3` suffixed leftovers from prior runs continue to resolve via the hardened scanner.
3. **Rollback strategy:** the change is confined to `lib/set_orch/` and `bin/`. If the circuit-breaker misfires, setting `merge_stall_threshold` to a very high number effectively disables it. The `--worktree` flag in `set-merge` has a fallback to discovery if omitted, so reverting the merger to not pass it is safe. The shared-helper call in `IssueManager` can be commented out to revert the aggressive cleanup behavior.

## Open Questions

- Should `cleanup_change_artifacts` also purge per-change files under `journals/<name>.jsonl` and `.set/orchestration/activity-detail-<name>.jsonl`? Current decision: **no**, those are retained for post-run forensics and are safe to keep across resets. Revisit only if operators report clutter complaints.
- Should the circuit-breaker threshold adapt to historical merge timing (e.g., "20 attempts or 10 minutes, whichever first")? Current decision: **attempt count only**, for simplicity. Time-based threshold can be added later if needed without schema changes.

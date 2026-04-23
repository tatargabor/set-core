## Context

The fix-iss pipeline creates a diagnostic child change for a parent that hit a circuit breaker. The parent is marked `failed:<reason>`, the child is dispatched, and once the child merges its fix the parent is unfailed via `_retry_parent_after_resolved` (the path we just hardened in `fix-merge-worktree-collision`). But there's a second auto-resolve path that predates the explicit retry flow:

**Native parent merge** — sometimes the parent's underlying problem resolves without the fix-iss child being needed. E.g. a token-runaway was caused by a transient decompose loop that self-corrected; by the time the fix-iss investigator wakes up, the dispatcher has already re-run the parent and merged it. `_check_affected_change_merged` notices the parent is merged and transitions the issue to RESOLVED. Good so far — but the linked fix-iss child (already claimed via `_claim_fix_iss_dir`, already registered in `state.changes` by `_register_fix_iss_in_state`) stays behind as `pending`. The next dispatcher cycle sees a pending change with a proposal, picks it up, spawns an agent. The agent has no context (parent is merged, nothing to fix) and typically emits confused commits or stalls.

A second, operator-driven gap: when a user manually cleans orphan fix-iss children (rm -rf on the dir + state edit), `escalate_change_to_fix_iss` has no idea. If the same parent hits a circuit breaker again, the function scans `openspec/changes/` for the max existing NNN, bumps by one, and creates a new `fix-iss-NNN-<slug>` — which can collide in spirit (same parent → two fix-iss children over time, the first silently orphaned).

Both gaps fit the same lifecycle model: **a fix-iss child's lifetime is anchored to the parent's need for it**. When the need ends (parent merged natively, or parent resolved through the child's own fix), the child must be closed out. When the need re-appears, the first thing to check is whether a prior child is still live.

## Goals / Non-Goals

**Goals:**
- Make native-parent-merge auto-resolve leave no orphan fix-iss artifacts on disk or in state.
- Prevent silent double-escalation: one parent → one active fix-iss child at a time.
- Provide an operator CLI for retroactive cleanup so projects that already accumulated orphans (from prior runs before this change) can be cleaned up once.

**Non-Goals:**
- Reconciling historical orphan fix-iss children inside archived changes (`openspec/changes/archive/`). Out of scope.
- Changing the circuit-breaker → fix-iss escalation semantics for new cases (token_runaway, retry_budget_exhausted, merge_stalled) — those work correctly.
- Cross-parent merge: if fix-iss child N is resolving parent A and a sibling parent B has its own (linked) fix-iss child, each link stays distinct. We do not coalesce siblings.
- Renaming fix-iss children or changing the `fix-iss-NNN-<slug>` naming convention.

## Decisions

### D1: Cleanup helper name and placement

**Decision:** Add `_purge_fix_iss_child(issue, state_file, project_path, *, reason)` as a module-level function in `lib/set_orch/issues/manager.py`. Private (`_`-prefixed), not exposed via `__init__.py`. Accessed from two call sites: `_check_affected_change_merged` and the new `set-orch-core issues cleanup-orphans` CLI handler.

**Alternative considered:** Put this in `lib/set_orch/change_cleanup.py` next to `cleanup_change_artifacts`. Rejected because this function operates on *state entries and openspec directories* (no git worktree/branch concern), which is a different domain. Keeping it in `issues/manager.py` where the other fix-iss lifecycle code lives (_register_fix_iss_in_state, _claim_fix_iss_dir) preserves cohesion.

### D2: When to purge — the "safe to remove" predicate

**Decision:** `_purge_fix_iss_child` removes the fix-iss child only when ALL of the following are true:

1. `issue.change_name` is set AND starts with `fix-iss-`.
2. The state entry for `issue.change_name` exists AND its status is one of: `pending`, `stopped`, `stalled`, `failed:*` — i.e., NOT `dispatched`, `running`, `verifying`, `merged`, `integrating`.
3. The corresponding `openspec/changes/<name>/` dir either (a) exists and has no agent worktree currently active for it, or (b) is already gone.

If the child's state is `merged`, the fix landed for real — no orphan, nothing to purge. If `dispatched`/`running` etc., an agent is actively working on it — removing mid-flight is unsafe; we log WARN and skip, letting the natural flow complete.

**Rationale:** Aggressive cleanup would kill in-flight legitimate work. The predicate above matches the incident pattern (the fix-iss child sat `pending` on the phase gate because the parent merged first), not active dispatches.

### D3: Idempotency in `escalate_change_to_fix_iss`

**Decision:** Before calling `_claim_fix_iss_dir`, read `parent.fix_iss_child` from state. If set:

- If `state.changes` has an entry with that name AND its status is NOT in (`merged`, `merge-failed`, `integration-failed`), AND the `openspec/changes/<name>/` dir exists on disk → treat as "already escalated", log INFO, return the existing name (no new claim, no new proposal write).
- If any of those three checks fails (entry missing, status terminal-but-failed, dir missing) → log WARN noting the inconsistency, then proceed with a fresh escalation.

**Alternative considered:** Use a refcount or a "generation" field. Rejected as over-engineering — the simple "is the prior link still live?" check covers the observed incidents.

### D4: CLI shape and safety

**Decision:** Add `set-orch-core issues cleanup-orphans [--project <name>] [--dry-run] [--yes]`. Default behavior lists each orphan candidate with: parent name, parent status, issue state, child state-entry status, dir presence. Without `--yes`, requires interactive confirmation. `--dry-run` lists without confirming and without modifying.

Orphan criteria (the CLI applies the SAME predicate as D2 PLUS one additional case):

- Parent change is in `state.changes` with status `merged` AND the linked fix-iss child is still `pending`/`stopped` → orphan (auto-resolve worked, cleanup didn't).
- Issue state is `RESOLVED`/`DISMISSED`/`MUTED`/`CANCELLED` AND the linked fix-iss child state entry exists with non-terminal status → orphan.
- fix-iss directory exists on disk but no state.changes entry AND no live issue → orphan (operator-induced divergence).

### D5: Logging and audit contract

**Decision:** Every orphan purge emits:

- INFO log with the fix-iss name, parent name, reason (`parent_merged` / `issue_resolved_manually` / `fs_state_divergence`), and whether the state entry + dir were removed.
- Audit entry `fix_iss_orphan_purged` on the triggering issue (if still in the registry), with the same fields.

## Risks / Trade-offs

- **[Risk] False-positive purge while an agent is dispatching the fix-iss child** — if there's a narrow window where the state entry is `pending` but dispatch is about to flip it to `dispatched`. → Mitigation: D2's safe-remove predicate excludes `dispatched`/`running`. The window is small (milliseconds between `dispatch_ready_changes` selecting the change and the first state write), and the auto-resolve path only runs on issues, not on the dispatcher's main tick — so they do not interleave at high frequency.
- **[Risk] Idempotency guard in D3 masks a legitimate re-escalation need** — if an operator wants to force a new fix-iss for a parent that already has one linked. → Mitigation: the CLI (`set-orch-core issues cleanup-orphans`) lets operators detach a stale link cleanly before re-triggering. For scripted re-escalation the caller can pre-clear `parent.fix_iss_child` in state. We do NOT provide a `force=True` flag on `escalate_change_to_fix_iss` — too easy to misuse.
- **[Trade-off] D2 is conservative — it refuses to purge `dispatched` orphans** — in rare cases (agent crashed mid-run, zombie PID) this could leave an orphan that the auto-path won't touch. The CLI fills this gap: operators can review and confirm manual cleanup of such edge cases. Documented in the CLI help text.

## Migration Plan

1. No state migration. The new `_purge_fix_iss_child` only activates when the native-merge auto-resolve path fires on a fresh case.
2. Pre-existing orphans from prior runs are cleaned up by the new CLI (`set-orch-core issues cleanup-orphans --dry-run` first, then without `--dry-run` after reviewing).
3. Rollback strategy: if the auto-purge misfires, revert just the `_check_affected_change_merged` hook call; the helper remains callable via the CLI. No persistent state side-effects that need undoing.

## Open Questions

- Should the CLI also clean up `journals/<fix-iss-name>.jsonl` and related per-change artifacts? Current decision: **no**, journals are forensic records and low-cost to retain. Revisit if operators report clutter.
- Should the idempotency check in D3 auto-clear a dead `parent.fix_iss_child` link (i.e. if the dir is gone, NULL the field)? Current decision: **yes**, clear the stale link as part of the WARN-then-proceed path, so future escalations see a clean slate.

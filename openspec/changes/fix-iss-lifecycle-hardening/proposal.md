# Proposal: fix-iss-lifecycle-hardening

## Why

When the orchestrator merges a change whose auto-escalated fix-iss child was still pending (e.g. the parent's underlying issue resolved naturally and the dispatcher picked the parent back up), the issue manager detects the parent merge and auto-resolves the issue, but it leaves the linked fix-iss change behind:

- The fix-iss entry stays in `state.changes` as `pending`
- The `openspec/changes/fix-iss-NNN-<slug>/` directory stays on disk with a stale proposal

On the next monitor cycle, the dispatcher picks up the orphan as a normal pending change and spawns an agent against a proposal that describes a problem no longer relevant — wasted tokens, potentially misleading "fix" commits.

A second related hygiene gap: `escalate_change_to_fix_iss` is not idempotent in the presence of operator-driven purges. If the parent already has a linked `fix_iss_child` but the user manually deleted the corresponding directory, a later escalation for the same parent will silently create a new fix-iss with a fresh `NNN` — resulting in two logically-duplicate escalations without the first being marked closed.

Both gaps are in the same subsystem (`issues/manager.py`) and share the same cleanup primitives. Fixing them together continues the lifecycle-hygiene work started in `fix-merge-worktree-collision`.

## What Changes

- **NEW helper** `_purge_fix_iss_child` in `lib/set_orch/issues/manager.py` — removes a fix-iss child's state entry and its openspec directory, idempotent against already-purged artifacts.
- **MODIFIED** `_check_affected_change_merged` — after transitioning to RESOLVED because the parent merged, call `_purge_fix_iss_child(issue)` to drop the orphan fix-iss.
- **MODIFIED** `escalate_change_to_fix_iss` — before claiming a new `fix-iss-NNN-<slug>` dir, check whether the parent already has a linked `fix_iss_child` that is still present in state AND on disk. If so, return the existing name (no-op re-escalation). If the link points at a missing dir/state entry, log WARN and allow a fresh escalation to proceed.
- **NEW CLI** `set-orch-core issues cleanup-orphans --project <name>` — scans the registry, state, and filesystem for orphan fix-iss artifacts (parent merged / RESOLVED / DISMISSED / MUTED / CANCELLED, but state entry or dir lingering) and removes them after confirmation. `--dry-run` supported.

## Capabilities

### New Capabilities
- `fix-iss-orphan-cleanup` — Single-source cleanup contract for orphan fix-iss children: state entry + openspec directory removal, idempotent, callable from auto-resolve hooks and from a manual CLI.

### Modified Capabilities
- `issue-state-machine` — Auto-resolve via native parent-merge now cleans up the linked fix-iss child. Escalation is idempotent against existing parent↔child links.

## Impact

- Modified: `lib/set_orch/issues/manager.py` (new helper + two existing functions touched).
- Modified: `bin/set-orch-core` (new subcommand) OR a focused helper that the CLI dispatches to.
- No schema changes. No new state fields. No migrations.
- Backwards-compatible: projects with no orphan fix-iss children see no behavior change; the idempotency guard in `escalate_change_to_fix_iss` only activates when a prior link exists.

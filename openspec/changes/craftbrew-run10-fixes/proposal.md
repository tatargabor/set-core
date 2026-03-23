# Proposal: Craftbrew Run #10 Fixes

## Problem

Craftbrew-run10 E2E run exposed 5 framework bugs that required manual intervention. While cycle 1 achieved 6/6 merged, each merge needed hand-holding due to engine/merger/ralph loop issues.

## Bugs Found

1. **Duplicate worktree dispatch** (HIGH) — Engine dispatches the same change twice, creating `-2` suffix worktrees. No guard in `dispatch_all_ready()` against dispatching already-running changes.

2. **Merge-blocked infinite retry loop** (CRITICAL) — When integration build gate fails, `retry_merge_queue` re-adds to queue endlessly with no max retry count.

3. **Stalled agent with completed tasks** (MEDIUM) — Ralph loop declares "stalled" (commit repetition) even when all tasks are `[x]`. Stall detection runs before done check.

4. **Missing vitest in planning rules** (HIGH) — Planning rules don't explicitly mandate test script in package.json for infrastructure changes. Agents skip vitest setup.

5. **Prisma pre-build: seed is wasteful** (LOW) — `e2e_pre_gate` runs full seed before build gate, but build only needs `db push` (schema sync), not seed data.

## Solution

Fix all 5 issues in the respective files. Add planning rule for vitest. Add integration pre-build hook separate from e2e_pre_gate.

## Scope

- `lib/set_orch/dispatcher.py` — duplicate dispatch guard
- `lib/set_orch/merger.py` — merge retry counter + dedicated pre-build hook
- `lib/loop/engine.sh` — reorder done check before stall detection
- `modules/web/set_project_web/planning_rules.txt` — vitest requirement
- `modules/web/set_project_web/project_type.py` — `integration_pre_build()` method
- `lib/set_orch/profile_types.py` — ABC for `integration_pre_build()`

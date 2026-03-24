# Design: Simplify Merge Policy

## D1: Always queue done changes

**Decision:** Remove the `if merge_policy in ("eager", "checkpoint")` guard in `verifier.py:2767`. Always add done changes to the merge queue.

The merge queue + integration gates ARE the quality control. Skipping the queue (manual policy) means no integration gates — which contradicts the "never merge manually" rule.

## D2: Keep checkpoint code, remove from template

**Decision:** Don't delete checkpoint infrastructure (engine.py checkpoint loop, milestone.py, API approve endpoint). It's working code that could serve production use cases. Instead:

- Remove checkpoint settings from `modules/web/.../config.yaml` template
- Remove checkpoint config injection from `tests/e2e/runners/run-craftbrew.sh`
- Keep `checkpoint` as valid config value (backwards compat)
- Remove `manual` from config enum (it contradicts gate-only rule)

## D3: Race condition safety with eager

With eager, the merge flow is: done → queue → integrate → gates → ff-only. The race conditions from run #11 are already fixed:

- **Dirty files:** stash in `_integrate_for_merge()` (commit `e9e395cc6`)
- **FF-only branch ref:** diagnostics in set-merge (commit `9f00a4bd4`)
- **Infinite retry:** counter check in `execute_merge_queue()` (commit `9f00a4bd4`)
- **Stalled recovery:** `_poll_suspended_changes()` handles stalled (commit `9f00a4bd4`)

No additional merge safety needed — eager with integration gates is safer than checkpoint+auto_approve because it's simpler (fewer code paths = fewer bugs).

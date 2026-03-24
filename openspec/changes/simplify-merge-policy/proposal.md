# Proposal: Simplify Merge Policy

## Why

The `merge_policy` config option offers 3 choices (eager/checkpoint/manual) but in practice ALL E2E runs use `checkpoint + checkpoint_auto_approve: true`, which behaves identically to `eager`. The checkpoint infrastructure adds complexity without value — nobody sits and manually approves checkpoints during orchestration runs. The `manual` policy contradicts the sentinel autonomy rule ("NEVER merge manually").

Run #11 post-mortem confirmed: the merge policy was NOT the cause of any failures. The dirty file, retry counter, and ff-only bugs were the actual issues, all now fixed.

## What Changes

- **Default merge_policy → eager** (was "eager" in code, but template overrode to "checkpoint")
- **Template config cleanup** — remove checkpoint_auto_approve, checkpoint_every from template
- **Always add to merge queue on done** — remove the `if merge_policy in ("eager", "checkpoint")` guard, always queue
- **Keep checkpoint code** — don't delete, just make it opt-in for future production use case
- Remove `manual` from valid policy enum (contradicts gate-only merge rule)

## Capabilities

### Modified Capabilities
- `merge-policy-config` — Default to eager, remove manual, checkpoint stays opt-in

## Impact

- `lib/set_orch/verifier.py` — remove merge_policy guard on queue add
- `lib/set_orch/engine.py` — default Directives.merge_policy = "eager"
- `lib/set_orch/config.py` — remove "manual" from enum
- `modules/web/.../config.yaml` — remove checkpoint settings from template
- `tests/e2e/runners/run-craftbrew.sh` — remove checkpoint config injection

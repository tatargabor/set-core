## Why

The fleet screen's stage strip showed `apply` for a change the session had already
ARCHIVED (user-reported with a screenshot, 2026-08-30). Measured cause: the
session→change inference ranks candidates purely by recency, and the session's verify
work had merely REFERENCED another session's active change — 2 invocation matches, most
recent — which outranked the session's own just-archived change. Recency alone cannot
tell a session's own work from a drive-by mention of someone else's.

## What Changes

- New capability spec `agent-stage-derivation`, documenting retroactively what the
  resolver already did (derived vs declared precedence, the artifact→stage mapping,
  named gaps) and adding the one new rule:
- **The archive anchor**: when the most recent positionable candidate is NOT archived,
  and some other candidate derives to `archive` with at least half the leader's
  tail-window mention weight, the archive wins. Finished work stays finished until the
  session's new work outweighs it.
- The inference exposes per-candidate tail-mention counts (weights) alongside the
  recency-ordered list; the in-memory memo now holds slugs and COUNTS — never
  transcript content.

## Capabilities

### New Capabilities

- `agent-stage-derivation`: how an agent row's flow and position are resolved from the
  project's openspec tree (or a producer's declared stage order), including the
  candidate inference and the archive anchor.

### Modified Capabilities

(none)

## Impact

- `lib/set_orch/fleet/stage.py` — the inference and the derived path of `resolve_stage`.
- No UI change: the strip renders whatever position the payload carries.

## Why

The orchestration engine (`engine`, `planner`, `dispatcher`, `verifier`, `merger`, `digest`,
`gate_runner`, `recovery`, `reporter`, `watchdog`, `milestone`, `auditor`, `builder`, `loop`,
~29k lines) and the sentinel/supervisor/manager layer are loaded by no live entry point except
lazily through the dashboard's sentinel API; no orchestration state changed in any registered
project in 30 days. Its web pages and API routes (`api/orchestration`, `sessions`, `actions`,
`learnings`, `lineages`, `_sentinel_orch`, the dashboard/plan/DAG/gate/digest views) display that
dormant state. Stage 5 of `fleet-era-consolidation`.

## What Changes

- Remove the engine modules, the sentinel/supervisor/manager layer (keeping `issues` only if
  something live reads it), their API routes, the matching React pages and components, and their
  tests. **BREAKING** — the orchestration feature is gone.

## Precondition

- A week of route-hit counts from the dashboard (there is no access log today — add one first),
  showing the routes to be removed are not opened.
- The fleet view and project status import nothing from the removed modules.
- A regression-baseline set diff before and after.

## Impact

`lib/set_orch/` (most of it), `web/src` (a large part), `tests/unit` (a large part), the docs that
describe orchestration, consumer rules about orchestration in `templates/core/rules/`.

> **Superseded 2026-11-23 — closed without implementing the open tasks.** This change extends the
> orchestration engine (E2E gates, decompose/planner, fix-iss, the web project template and the
> run dashboards), which `fleet-era-consolidation` retires (stages 4-5: `retire-orchestration-cli`,
> `retire-orchestration-engine`). Archived with `--skip-specs` semantics: no delta reached
> `openspec/specs/`. Tasks ticked here were shipped; unticked ones were not.

## Why

The the design tool v2 run exposed a pattern where a single change (`websocket-server-and-brain`) implemented 44/45 tasks with 98% test pass rate in 59 minutes, then spent 2+ hours and 24 retries failing to merge because:
1. The E2E gate's retry context said "suite crashed before completing" without the webServer stderr that explained WHY (port conflict, missing module, wrong start command)
2. The agent retried 12× with identical context, degrading from 15-minute attempts to 3-minute "give up immediately" cycles (learned helplessness)
3. The fix-iss agent spent ~1 hour creating openspec artifacts (proposal, design, specs, tasks) before touching any code — unnecessary ceremony for a diagnostic fix
4. Integration smoke gate failed on 4 pre-existing test failures that also fail on main — the agent spent 2+ hours debugging React 19 hydration timing issues that weren't caused by its change

## What Changes

- **webServer log in e2e retry context**: When the E2E gate fails with a webServer timeout or no parseable failure list, include the last N lines of webServer stderr/stdout in the retry context. The agent needs to see "Error: Cannot find module './server.ts'" or "EADDRINUSE port 3000" to know what to fix.
- **No-commit retry detection**: Before incrementing `verify_retry_count`, compare the current HEAD against the last gate commit (`last_gate_commit`). If HEAD hasn't changed, the agent didn't commit anything new — log a warning and don't consume retry budget.
## Capabilities

### New Capabilities

_None — all fixes modify existing capabilities._

### Modified Capabilities

- `verify-gate`: No-commit retry detection (compare HEAD vs last_gate_commit before incrementing retry count)
- `web-gates`: webServer log capture in e2e retry context; extract and include webServer stderr when Playwright crashes or times out

## Impact

- **Web module** (`modules/web/set_project_web/gates.py`): E2E gate retry context enrichment — extract webServer logs from combined output, include in retry_context when gate fails without parseable failures
- **Core verifier** (`lib/set_orch/verifier.py`): No-commit retry detection at verify_retry_count increment site
- **No breaking changes**: All changes are additive improvements to existing flows with safe fallbacks

## Out of Scope

- **Integration smoke baseline comparison** (running inherited specs on main for pre-existing failure detection) — separate change, needs architectural decisions around main checkout vs cached baseline
- **fix-iss openspec ceremony skip** — the ceremony provides tracability; with the webServer log and no-commit guard fixes, fix-iss triggers less often and the 1h ceremony cost is acceptable

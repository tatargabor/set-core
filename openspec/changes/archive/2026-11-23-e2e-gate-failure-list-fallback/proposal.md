> **Superseded 2026-11-23 — closed without implementing the open tasks.** This change extends the
> orchestration engine (E2E gates, decompose/planner, fix-iss, the web project template and the
> run dashboards), which `fleet-era-consolidation` retires (stages 4-5: `retire-orchestration-cli`,
> `retire-orchestration-engine`). Archived with `--skip-specs` semantics: no delta reached
> `openspec/specs/`. Tasks ticked here were shipped; unticked ones were not.

## Why

When the E2E gate fails with `exit_code != 0` but Playwright did not emit a parseable failure list (suite crashed before completing — webServer startup error, OOM, reporter misconfiguration, hung worker), the gate produces a `retry_context` that says "Playwright did not emit a failure list — check the worktree for stack traces" but does NOT include those stack traces. The fix-iter agent receives the prompt with no concrete error to act on and has to read trace ZIP files in `test-results/` to find what crashed — burning a session on diagnosis before any fix work begins. Observed pattern: changes hit this code path twice in succession, each iteration costing 2-5 minutes of agent time on rediscovering information the gate already had.

## What Changes

- The E2E gate's "no parseable failure list" `retry_context` SHALL include the last N lines of `e2e_output` (default 80) inline so the agent sees the actual stderr/stdout tail immediately. The cap prevents context bloat; the existing classification line stays.
- Lines containing common crash markers (`Error:`, `Traceback`, `webServer`, `Killed`, `OOM`, `assert`) SHALL be included regardless of position in the output (preserved as a "matched markers" section above the tail).
- The existing fallback message ("This usually means the suite crashed...") SHALL be retained as the orientation paragraph; the inline output appears below it under a clearly-labeled `## Stdout/stderr tail (last N lines)` heading.

## Capabilities

### New Capabilities
- `e2e-gate-failure-context-tail`: inline-output behavior for the unparseable-failure path of the E2E gate.

### Modified Capabilities
(none — purely additive content in retry_context)

## Impact

- **Code**: a single function in `modules/web/set_project_web/gates.py` (the no-`wt_failures` branch around line 1613-1648). Add a helper `_build_failure_tail(e2e_output: str, max_lines: int = 80) -> str` and call it.
- **Behavior**: agents on the unparseable-failure path get actionable error text in their first iteration instead of "go look at the worktree". The retry session that previously discovered the trace converges to a fix iteration immediately.
- **Observability**: `retry_context` becomes longer when this path fires (typically +3-5KB). Acceptable — context is gated by retry-budget-aware caching, not by raw size.
- **Backwards compat**: agents that already cope with the terse message continue to work — the new text is additive. No public API changes.
- **Out of scope**: changing classification logic, adding new gates, modifying the parseable-failure-list path, or modifying retry counts/budgets.

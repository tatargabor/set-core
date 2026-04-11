# Block Integration E2E Smoke Failures

## Why

The merger's integration e2e gate runs in two phases (`lib/set_orch/merger.py:1215-1295`):

- **Phase 1 — Inherited smoke tests**: runs the first test from each sibling spec file against the merged worktree. Purpose: detect cross-change contamination where the merging change breaks a test owned by a previously-merged change (e.g. a new admin form creates DB rows that break a sibling listing page's count assertion).
- **Phase 2 — Own tests**: runs the merging change's own spec files. Blocking.

**Phase 1 is currently non-blocking.** When a smoke test fails, `merger.py:1266-1274` logs a WARNING "regression possible", sets `_smoke_failed = True`, and **continues to Phase 2**. If Phase 2 passes, the merge proceeds — even though a sibling test just regressed. The `_smoke_failed` flag is only surfaced in the retry context IF Phase 2 later fails.

This directly caused ~70 minutes of waste in a recent run: a change's admin CRUD tests created DB rows that made a sibling change's storefront listing fail its exact-count assertion. The smoke phase caught it and logged a warning — then the change merged anyway. The regression only surfaced after the merge, when a later verify cycle noticed the broken state, triggered a full redispatch, rebuilt the worktree, re-ran every gate, and re-reviewed the change. Two redispatches, one hour of wall time, all preventable if smoke had blocked the merge.

The design intent of smoke-as-warning was "don't punish a change for a test the other team owns". That intent is preserved with a directive flag — operators can opt out — but the default must be **block** so that in the common case (one team, one orchestration run, shared DB), regressions fail fast.

## What Changes

- **Smoke phase becomes blocking by default.** When Phase 1 fails, the merger:
  1. Sets `e2e_result = "fail"` on the change
  2. Triggers the same redispatch logic that Phase 2 failures use, with a retry context that explains the smoke failure and lists the failing sibling spec files
  3. Does NOT proceed to Phase 2 (no point running own tests when the merged state is broken)
- **New directive `integration_smoke_blocking: bool = True`.** Operators who explicitly want the old non-blocking behavior (independent teams, tolerant of transient regressions) can set this to `false` in `orchestration/config.yaml`. The framework default is `true`; the Next.js web template default is `true`.
- **Retry context enhancement**: the retry prompt points the agent at the failing sibling specs by name and explains that the change is likely polluting shared state (DB rows, `.next/` cache, session cookies) which breaks tests it does not own. Hint: use per-test cleanup, unique names, or `test.afterEach(...)` teardown.

## Capabilities

### Modified Capabilities
- `merger-gate-integrity` — the integration e2e smoke phase blocks the merge when it fails, unless the operator opts out via directive.

## Impact

- **`lib/set_orch/merger.py`** (around lines 1250-1295): the smoke-fail branch replaces the WARNING+continue logic with a block-and-redispatch path. Phase 2 is skipped when smoke blocked. The `_smoke_failed` flag stays for compatibility with downstream log/event consumers but is now paired with a real redispatch.
- **`lib/set_orch/engine.py`** (`Directives` dataclass): new field `integration_smoke_blocking: bool = True`, parsed in `parse_directives`.
- **`modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml`**: no change — the new field inherits the framework default (`true`).
- **Tests**: new `tests/unit/test_merger_smoke_blocking.py` with three cases: smoke fails → merge blocked + redispatch, smoke passes → merge proceeds, directive override (`false`) → warning-only (old behavior).
- **Backwards compat**: runs that set `integration_smoke_blocking: false` explicitly keep the old behavior. Existing runs without the directive get the safer default.
- **Risk**: a smoke test that is flaky on main will now block merges. Mitigation: the baseline comparison from `fix-e2e-gate-timeout-masking` already filters pre-existing failures out of `wt_failures`, so stable-flaky tests on main do not trip the smoke gate. A genuinely flaky test that passes on main but fails inconsistently in the merged state is the only remaining risk, and it is the correct signal — such tests should be marked `@flaky` and excluded from smoke.

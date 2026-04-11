# Reduce Change Retry Waste

## Why

End-to-end runs show that a single difficult change can balloon to 4× the average time due to redispatch loops. The root causes break down cleanly:

1. **Late spec discovery**: `spec_verify` runs AFTER `review`, so deep specification gaps (e.g. a required entity is never persisted) are only caught on the second or third retry cycle. The review gate cannot fail on spec coverage — it lacks the structured spec comparison logic — so its first-pass PASS gives a false sense of progress.
2. **Retry limit drift**: `e2e_retry_limit` has two different defaults in the codebase — `5` in `lib/set_orch/engine.py:64` (directive class), `3` in `lib/set_orch/merger.py:1704` (runtime fallback). A run can silently behave differently depending on whether the directive is set.
3. **Missing Playwright isolation rules**: The web template covers SQLite single-writer constraints and unique-column generation, but has no rule for:
   - Exact-count assertions (`toHaveCount(6)`) in suites that share a DB across specs — one change creating test rows breaks a sibling change's count assertion.
   - `getByLabel` prefix ambiguity (e.g. `"Description"` matches both `"Description"` and `"Short Description"`) needing `{ exact: true }`.
   - `toHaveURL` regex that matches intermediate auth routes (e.g. `/\/admin/` matches `/admin/login`), leading to login races.

Combined, these cause the retry waste: specification gaps get "fixed" twice (once for review style issues, again when spec_verify finally catches the spec violation), and Playwright bugs re-surface across redispatches because the agent never sees a rule that would prevent them in the first place.

## What Changes

- **Reorder verify pipeline**: run `spec_verify` before `review`. Spec gaps should block the pipeline before the expensive review+retry loop begins.
- **Unify integration-e2e retry limit default**: single source of truth for the default value, readable from both `engine.py` and `merger.py`.
- **Add 3 Playwright isolation rules** to the web template `testing-conventions.md`:
  - Ban exact-count assertions against DB-backed counts — use `{ min: N }` instead.
  - Require `{ exact: true }` on `getByLabel` when the label text is a prefix of another label on the same page.
  - Require exclusionary regex on `toHaveURL` when the target path is a substring of an intermediate route.

## Capabilities

### Modified Capabilities
- `verify-pipeline-order` — reorder gates so spec_verify runs before review
- `integration-retry-defaults` — unify the e2e_retry_limit default between directive and merger fallback
- `web-testing-conventions` — extend Playwright conventions with 3 isolation rules

## Impact

- **`lib/set_orch/verifier.py`**: Swap gate registration order (lines 3015-3032). The `review` registration moves AFTER `spec_verify` and after `rules`. No execution logic changes — just the order the pipeline runs them.
- **`lib/set_orch/engine.py`** / **`lib/set_orch/merger.py`**: Replace the duplicated literal default. Both sites read from a single module-level constant.
- **`modules/web/set_project_web/templates/nextjs/rules/testing-conventions.md`**: Three new sections appended.
- **No schema or state changes**: fields stay the same, only execution order and rule text change.
- **Backwards compat**: existing changes mid-run continue to work. The retry limit default change surfaces only for new runs (directive is read per-run).
- **Risk**: reordering review/spec_verify could mask review findings if spec_verify fails loud and early — mitigated by keeping review in the pipeline, not removing it.

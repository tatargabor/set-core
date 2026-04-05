# Change: e2e-smoke-functional-split

## Why

Currently the E2E integration gate runs **all** Playwright tests in the worktree — including tests from previously merged changes. Real data from craftbrew-run22:

| Change (merge order) | Own spec file(s) | Total tests run | Gate time |
|---|---|---|---|
| foundation-setup | `foundation.spec.ts` | 18 | skipped |
| auth-and-profile | `auth.spec.ts` | 24 | 43s |
| product-catalog | `catalog.spec.ts` | 24 | 14s |
| content-email-wishlist | `content.spec.ts` + `wishlist.spec.ts` | 37 | 64s |
| cart-and-promotions | `cart.spec.ts` | 44 | 67s |
| admin-panel | `admin.spec.ts` | 53 | **130s** |

By change #6, the gate runs 53 tests but only ~9 are from that change — the other 44 are inherited from prior changes. When inherited tests fail (flaky, env issue), the agent gets redispatched to "fix" tests it didn't write and can't meaningfully fix.

## Key Constraints from Real Data

1. **Spec file names don't match change names**: `cart-and-promotions` → `cart.spec.ts`, `content-email-wishlist` → `content.spec.ts` + `wishlist.spec.ts`. A name-based glob won't work.
2. **Tests don't use REQ-* prefix** (except foundation). Tag-based filtering (`@smoke`) won't work retroactively.
3. **The actual E2E execution is inline in `merger.py:_run_integration_gates()`** (lines 982–1052), NOT `gates.py:execute_e2e_gate()`. The fix must target the merger.
4. **Must work immediately on existing runs** without requiring agents to re-tag their tests.

## What Changes

### 1. Git-based spec file ownership detection

New helper: `_detect_own_spec_files(wt_path, change_name) -> list[str]`. Uses `git diff <merge-base> --name-only --diff-filter=A` to find which `.spec.ts` files the change branch added. This works for any run, past or future, regardless of file naming conventions.

Fallback chain: git diff → `e2e-manifest.json` (if exists) → run all tests (current behavior).

### 2. Two-phase E2E gate in merger.py

Split the inline E2E execution in `_run_integration_gates()` into two phases:

- **Phase 1 — Inherited tests (smoke/regression)**: Run only the spec files NOT owned by this change. These are sanity checks — did merging main break something? Use `npx playwright test <inherited-files>`. **Non-blocking** — failures are logged as warnings + sent to sentinel, NOT redispatched to the agent. The agent can't fix someone else's tests.
- **Phase 2 — Own tests (functional)**: Run only the change's own spec files. These verify the new feature works. **Blocking** — failures trigger the existing redispatch/retry logic.

If Phase 1 has 0 inherited files (first change), skip to Phase 2. If Phase 2 has 0 own files, run all tests (fallback to current behavior).

### 3. Redispatch context scoping

When Phase 2 fails and the agent is redispatched, the retry context should ONLY include the failing tests from the change's own spec files — not inherited test failures. This prevents the agent from wasting cycles on tests it didn't write.

### 4. Test plan: `type` field on TestPlanEntry

`TestPlanEntry` gains `type: str = "functional"`. `generate_test_plan()` marks the first happy-path entry per requirement as `"smoke"`, rest as `"functional"`. This is forward-looking: future agents will use `{ tag: '@smoke' }` on smoke tests, enabling faster Phase 1 via `--grep @smoke` instead of file-based splitting.

### 5. Dispatcher: smoke/functional labels + e2e-manifest.json

The `## Required Tests` section labels entries `[SMOKE]` / `[FUNCTIONAL]` and instructs agents to use Playwright `{ tag: '@smoke' }` on smoke tests. During dispatch, write `e2e-manifest.json` to worktree root listing the change's expected spec files — used as ownership fallback when git diff is unavailable.

### 6. Coverage tracking: own vs inherited breakdown

`TestCoverage` gains `own_passed`, `own_failed`, `inherited_passed`, `inherited_failed` counts (more descriptive than smoke/functional since the split is by ownership). The dashboard can show these separately.

### 7. E2E methodology: agent instructions

`e2e_test_methodology()` updated to explain `@smoke` tagging convention for the first happy-path test per feature.

## Out of Scope

- Changing risk classification logic (already handled by ac-test-coverage-binding)
- Parallel test execution
- Phase-end E2E (verifier.py, separate concern)
- Changing `gates.py:execute_e2e_gate()` (not used by merger)

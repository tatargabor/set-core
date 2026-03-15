## Why

Playwright E2E tests run during the verify gate and phase-end, but produce only text-based `error-context.md` files (accessibility snapshots) instead of PNG screenshots. The verify pipeline collects `test-results/` contents and counts `.png` files — but finds zero because the generated `playwright.config.ts` lacks the `screenshot` setting (Playwright defaults to `'off'`). Users have no visual record of what the orchestrated build looks like after merge.

## What Changes

- Update the decompose template to instruct agents to include `screenshot: 'on'` in `playwright.config.ts`, so every E2E test produces a PNG alongside the existing text artifacts
- The existing collector pipeline (`verifier.py` per-change and phase-end) already copies `test-results/` and counts `.png` files — no collector changes needed

## Capabilities

### New Capabilities
- `e2e-screenshot-capture`: Playwright E2E tests produce PNG screenshots automatically via config, collected by the existing verify pipeline into `wt/orchestration/e2e-screenshots/`

### Modified Capabilities
<!-- None — the collector pipeline already handles PNG files correctly, it just never receives any -->

## Impact

- `lib/wt_orch/templates.py` — one line addition to the Playwright E2E planning section
- No new dependencies, no new functions, no runtime changes
- Backwards compatible — projects without Playwright or with custom configs are unaffected

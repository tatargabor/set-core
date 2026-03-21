# Proposal: e2e-gate-fix

## Why

The E2E verify gate silently skips in every orchestration run, even when `e2e_command` is configured and Playwright tests exist. Three independent bugs compound to guarantee the gate never executes: test discovery looks in hardcoded directories instead of reading the Playwright config, a health check probes a random port where no server is listening, and Playwright's built-in `webServer` auto-start is bypassed by the premature health check. The phase-end E2E path has similar port management issues.

## What Changes

- **Fix test discovery** to read `testDir` from `playwright.config.ts` instead of hardcoding `tests/e2e/`
- **Detect Playwright `webServer` config** and skip manual health check / port allocation when Playwright manages its own dev server
- **Add skip reason diagnostics** so every E2E skip includes an output message explaining why
- **Fix phase-end E2E** port management to match the same webServer-aware logic
- **Fix cleanup logic** to not pkill on wrong ports when Playwright manages the server

## Capabilities

### New Capabilities
*(none — this is a fix to existing capabilities)*

### Modified Capabilities
- `e2e-readiness-probe` — health check logic changes to be webServer-aware; test discovery uses Playwright config
- `verify-gate` — E2E gate skip reasons are now always populated in GateResult output

## Impact

- **Code**: `lib/set_orch/verifier.py` — `_execute_e2e_gate()`, `_count_e2e_tests()`, `run_phase_end_e2e()`
- **Config**: No new directives required (reads existing `playwright.config.ts` from project)
- **Backward compatible**: Projects without Playwright config or without `webServer` block continue to work as before (existing health check path preserved)

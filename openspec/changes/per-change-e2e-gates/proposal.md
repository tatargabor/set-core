# Change: per-change-e2e-gates

## Why

The current planner creates a FINAL "acceptance-tests" change that writes ALL E2E journey tests after all feature changes are merged. This caused multiple failures in craftbrew-run20:

1. **No regression detection**: when acceptance-tests agent fixes failing tests, it modifies app code to make tests pass — breaking previously working features. No gate catches this because the tests didn't exist when the earlier changes merged.
2. **Context overload**: one agent must understand ALL features to write cross-domain tests. It gets a 2751-char scope with 48 REQ-* IDs and 7 journeys — too much for reliable implementation.
3. **Retry hell**: when the big test suite fails the gate (9/53 failed), the retry agent has to fix tests across 7 journey files with no context about which change caused what.
4. **Contradiction in planning rules**: line 339 says "NEVER create standalone e2e change" but line 372 says "Always include FINAL acceptance-tests change".

## What Changes

### 1. Remove the acceptance-tests pattern from planner

Delete the "Acceptance test change (REQUIRED)" section (lines 371-428) from `templates.py`. The existing "Test-per-change requirement" rule (lines 366-369) already says each change must include its own tests — this is the correct pattern.

### 2. Strengthen per-change E2E rules

Update the "Test-per-change requirement" section to explicitly include E2E journey tests for cross-domain flows that the change introduces. Each change writes and runs its own E2E tests. The integration gate runs ALL E2E tests (existing + new) so regressions are caught immediately.

### 3. Default max_parallel to 1

Change `max_parallel` default from 3 to 1. Sequential execution prevents merge conflicts, shared state corruption, and port collisions. Document that >1 is experimental and can cause issues.

### 4. Move journey test methodology into per-change scope

The journey test methodology (PHASE 0/1/2) is valuable but currently embedded in the acceptance-tests scope. Move it to the profile's `acceptance_test_methodology()` so it's injected into EVERY change's scope, not just the final one.

## Impact

- `lib/set_orch/templates.py` — remove acceptance-tests section, strengthen per-change test rules
- `lib/set_orch/engine.py` — `max_parallel` default 3 → 1
- `modules/web/set_project_web/project_type.py` — move methodology to per-change injection

# Spec: per-change-e2e-gates

## Capability

Each orchestrated change includes its own E2E tests. The integration gate runs the full E2E test suite (all existing + new tests) so regressions are caught at the change that caused them. No separate acceptance-tests change exists.

## Behavior

### Planner rules
- Remove the "acceptance-tests" final change requirement from planning rules
- Resolve the contradiction: line 339 (never standalone e2e) vs line 372 (always include acceptance-tests)
- Each feature change's scope includes writing E2E tests for its features
- E2E test methodology (PHASE 0/1/2) is available to every change, not just a final one

### Integration gate
- Gate runs `npx playwright test` which executes ALL tests in `tests/e2e/`
- Previously merged changes' tests run alongside new tests
- If a previously-passing test fails → the current change broke it → current agent must fix

### Gate retry restriction
- Retry agent may only modify test files and test helpers
- Retry agent must NOT modify application source code
- If app behavior is wrong, document it but don't fix — that's the feature change's job

### Sequential execution
- `max_parallel` defaults to 1 (was 3)
- Configurable via `max_parallel` in orchestration config
- Document that >1 is experimental and causes merge conflicts, port collisions

# Change: e2e-test-enforcement

## Why

The ac-test-coverage-binding change built a complete test planning pipeline: `requirements.json` → `generate_test_plan()` → `test-plan.json` (226 scenarios, 494 expected tests for craftbrew). But the pipeline has three broken links that cause 87% under-coverage (67 actual tests vs 494 expected):

### Problem 1: digest_dir never reaches the dispatcher (FIXED)

`engine.py:_dispatch_ready_safe()` didn't pass `digest_dir` to `dispatch_ready_changes()`. Result: `_load_test_plan()` got empty string → no `## Required Tests` in input.md → 9/10 agents never saw their test plan entries.

**Fixed in `b864425`.**

### Problem 2: Replan changes lose requirements (FIXED)

`_append_changes_to_state()` didn't copy `requirements` field from plan to state. Phase 2 changes had 0 requirements → even with digest_dir fix, test plan entries wouldn't match.

**Fixed in `c3c359a`.**

### Problem 3: tasks.md overrides Required Tests (THIS CHANGE)

The planner LLM generates tasks.md with narratively-defined E2E tasks:
```
## 8. E2E Tests
- [ ] 8.1 Create tests/e2e/cart.spec.ts: cold visit shows empty, add product,
      qty +/-, remove, apply coupon, gift card preview.
```

The agent follows tasks.md (7 tests), ignoring the `## Required Tests` section in input.md which lists 39 entries with risk levels and category requirements (happy + negative). The agent never writes negative tests because the task doesn't ask for them.

### Problem 4: No gate enforcement of coverage

Even when the agent writes fewer tests than required, the E2E gate passes (tests pass = gate passes). The `validate_coverage()` function runs but is non-blocking — gaps are logged but never fail the gate. So an agent can write 7 tests when 39 are required and still merge.

## What Changes

### 1. Inject test-plan entries into planner prompt

When building the planning prompt, inject the test-plan.json entries per change's requirements. The LLM planner then sees the structured test expectations and generates tasks.md E2E sections that match — listing each REQ scenario with risk level and required test count, not a narrative summary.

### 2. Dispatcher: Required Tests override tasks.md E2E section

Make the `## Required Tests` section more authoritative. Add instruction: "The Required Tests list is MANDATORY — implement ALL listed tests. Your tasks.md E2E section is a subset; the Required Tests list is the complete set."

### 3. Coverage gate: blocking on feature changes

After E2E gate passes, run `validate_coverage()`. If coverage is below threshold (e.g., <80% of test-plan entries covered) for feature-type changes, treat as gate failure with redispatch context explaining which REQ scenarios are missing tests.

### 4. Planner: use test-plan.json to generate E2E tasks

New function `_inject_test_plan_into_scope()` reads test-plan.json, groups entries by the change's assigned requirements, and appends structured E2E task descriptions to the planning context. The LLM planner receives:

```
## Test Plan (from test-plan.json)
This change covers REQ-CART-001..REQ-PROMO-005 (39 test scenarios):
- REQ-CART-001: Cannot add without variant [MEDIUM] — 2 tests (happy, negative)
- REQ-CART-001: Returns error if qty > stock [MEDIUM] — 2 tests (happy, negative)
...
Generate E2E tasks that cover ALL scenarios. Do NOT reduce to a narrative summary.
```

## Out of Scope

- Changing risk classification logic (ac-test-coverage-binding)
- Two-phase gate execution (e2e-smoke-functional-split)
- Phase-end E2E (verifier.py)
- REQ-ID naming convention (already in methodology)

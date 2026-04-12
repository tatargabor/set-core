# Change: ac-test-coverage-binding

## Why

The AC (acceptance criteria) panel shows "no test" for scenarios that have passing E2E tests. From micro-web-run21:
- `REQ-HOME-001` "Hero heading visible on cold visit" → "no test" — BUT `navigation-and-home.spec.ts:4` tests exactly this
- `REQ-ABOUT-001` "About page company description" → "no test" — BUT `about-and-blog.spec.ts:4` tests it

The problem is three-fold:

1. **No naming convention binding**: Tests are named freely ("cold visit — heading and 3 team cards visible") with no reference to AC IDs (REQ-HOME-001, scenario "Hero heading visible")
2. **Coverage matcher is LLM-based**: The `parse_test_results()` → coverage mapping relies on fuzzy text matching, not deterministic ID binding
3. **Test planning is unstructured**: The planner tells agents "write E2E tests" but doesn't generate a structured test plan that maps AC scenarios → test cases

## What Changes

### 1. Python: deterministic AC→test binding via test name convention

Enforce a naming convention where each test includes the REQ-* ID:
```
test('REQ-HOME-001: Hero heading visible on cold visit', ...)
```

The coverage matcher then uses regex `REQ-[A-Z]+-\d+` extraction from test names — deterministic, no LLM.

### 2. Python: generate structured test plan from digest

After digest, Python generates a `test-plan.json` from the AC scenarios:
```json
[
  {"req": "REQ-HOME-001", "scenario": "Hero heading visible", "risk": "LOW", "test_cases": 1},
  {"req": "REQ-CONTACT-001", "scenario": "Form validation errors", "risk": "MEDIUM", "test_cases": 2}
]
```

Risk classification (ISTQB-inspired): HIGH (auth/payment/mutation) → 1 happy + 2 negative, MEDIUM (forms/state) → 1 happy + 1 negative, LOW (display/nav) → 1 happy only.

This plan is passed to each change agent in the dispatch context, NOT as LLM prompt but as structured data the agent must follow.

### 3. Python: post-gate coverage validation

After E2E gate passes, Python parses the Playwright output, extracts REQ-* IDs from test names, and compares against the test plan. Missing coverage → warning log (not blocking, but visible on dashboard).

### 4. Planner: inject test plan requirements per change

Each change's scope includes its relevant test plan entries. The agent sees:
```
Required tests (from test plan):
- REQ-HOME-001: Hero heading visible [LOW] → 1 test
- REQ-NAV-001: Navigation links present [LOW] → 1 test
Name each test with the REQ-* ID prefix.
```

## Impact

- `lib/set_orch/digest.py` — generate test-plan.json from AC scenarios
- `lib/set_orch/test_coverage.py` — deterministic REQ-ID matching from test names
- `lib/set_orch/dispatcher.py` — inject test plan entries into per-change input.md via `_build_input_content()`
- `modules/web/set_project_web/project_type.py` — update parse_test_results for REQ-ID extraction

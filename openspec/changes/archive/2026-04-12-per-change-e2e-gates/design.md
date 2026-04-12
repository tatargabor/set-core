# Design: per-change-e2e-gates

## Current flow (broken)

```
change-1 (foundation) → gate: build+test → merge (NO e2e tests exist yet)
change-2 (auth)        → gate: build+test → merge (NO e2e tests exist yet)
change-3 (catalog)     → gate: build+test → merge (NO e2e tests exist yet)
change-4 (cart)        → gate: build+test → merge (NO e2e tests exist yet)
change-5 (checkout)    → gate: build+test → merge (NO e2e tests exist yet)
change-6 (acceptance)  → writes ALL tests → gate: e2e → FAIL → retry →
                         modifies APP CODE to fix tests → regressions
```

## New flow

```
change-1 (foundation) → writes foundation e2e tests
                       → gate: build + test + e2e (foundation tests) → merge

change-2 (auth)        → writes auth e2e tests
                       → gate: build + test + e2e (foundation + auth tests) → merge

change-3 (catalog)     → writes catalog e2e tests
                       → gate: build + test + e2e (ALL previous + catalog) → merge
                         if previous tests fail → THIS change broke something → fix HERE

change-4 (cart)        → writes cart e2e tests
                       → gate: e2e (ALL tests) → merge

change-5 (checkout)    → writes checkout e2e tests
                       → gate: e2e (ALL tests) → merge
```

No separate acceptance-tests change. Each change owns its tests. The gate runs the FULL test suite so regressions are caught at the change that caused them.

## Implementation details

### 1. templates.py changes

Remove lines 371-428 (acceptance-tests section). The contradiction with line 339 is eliminated.

Strengthen lines 366-369 (test-per-change) to:
```
- Each change MUST include E2E tests for its features
- Tests go in tests/e2e/<change-name>.spec.ts
- The integration gate runs ALL tests in tests/e2e/ (not just new ones)
- If a previously-passing test fails, THIS change broke it — fix before merge
```

### 2. max_parallel default

```python
# engine.py line 54
max_parallel: int = 1  # Sequential execution; >1 is experimental
```

Why 1: sequential merges mean each gate runs against the complete state of all previous merges. No merge conflicts, no port collisions, no shared state corruption.

### 3. Python-side test failure classification

When the E2E gate fails, Python classifies failures BEFORE building the retry prompt:

```python
def _classify_test_failures(wt_path: str, e2e_output: str) -> dict:
    # 1. Get test files THIS change added/modified
    own_test_files = git diff --name-only main..HEAD -- tests/e2e/

    # 2. Parse failing tests from Playwright output
    failing = _parse_e2e_summary(e2e_output)["failing_tests"]

    # 3. Classify each failure
    own_failures = []      # test file is in own_test_files
    regression_failures = [] # test file is NOT in own_test_files

    for test in failing:
        test_file = extract_file_from_test_line(test)
        if test_file in own_test_files:
            own_failures.append(test)
        else:
            regression_failures.append(test)

    return {own_failures, regression_failures, own_test_files}
```

The retry prompt then has two structured sections:

```
## Your Test Failures (fix your test code or your app code)
- checkout.spec.ts:45 › 3-step checkout flow

## Regression Failures (your change broke a previously-passing test — fix YOUR app code, not the old test)
- auth-and-admin.spec.ts:70 › admin login
```

This way the LLM gets a **pre-classified** list, not a judgment call. Python decides what's a regression vs what's the change's own test, using git diff — deterministic, not LLM.

### 4. Per-change test methodology

Move the journey test methodology from the acceptance-tests scope section into the profile's per-change injection. The `acceptance_test_methodology()` return value gets appended to EVERY change's scope that includes E2E tests, not just the final one. Rename to `e2e_test_methodology()`.

### 5. Test file convention

```
tests/e2e/
├── <change-name>.spec.ts       ← each change writes ONE spec file
├── helpers/                    ← shared helpers (any change can add/extend)
│   ├── auth.ts
│   └── ...
└── global-setup.ts
```

- No `journeys/` subdirectory — flat structure in `tests/e2e/`
- Playwright `testDir: "./tests/e2e"` auto-discovers ALL `.spec.ts` files
- Gate runs `npx playwright test` → executes ALL specs (previous + new)
- Cross-domain tests go in the change that implements the LAST step of the flow
  (e.g., full purchase flow → checkout change, because it depends on catalog+cart)

### Why this works without extra config

The existing `npx playwright test` command already runs all `*.spec.ts` in `tests/e2e/`.
When a new change adds `checkout.spec.ts`, the gate automatically includes it alongside
`foundation.spec.ts`, `auth-and-admin.spec.ts`, etc. — zero config change needed.

Evidence from craftbrew-run20: foundation, auth, and catalog changes already wrote per-change
specs that the gate ran. Only cart and checkout skipped (because the "acceptance-tests"
rule gave them an out).

### 6. Retry limit and exhaustion flow (fix infinite loop)

**Current bug**: merge-blocked → `_recover_merge_blocked_safe` sees no active issues →
recovers to `done` → merge queue → gate fails → merge-blocked → recover → infinite loop.

**Fix**: when retry limit reached → `integration-failed` (terminal, not recoverable).
Remove from merge queue. The replan can create a new change if needed.

```
E2E FAIL + retry_count < limit:
  → status: integration-e2e-failed → engine redispatches → agent fixes → done → gate reruns

E2E FAIL + retry_count >= limit:
  → status: integration-failed (TERMINAL)
  → remove from merge_queue
  → replan can pick up uncovered requirements
```

Config: `e2e_retry_limit` in orchestration config (default 3).
Reset: `integration_e2e_retry_count` cleared in `resume_change()` alongside `merge_retry_count`.

# Design: gate-retry-context

## Current Flow

retry_ctx is built in **two places** with the same flat format:

1. `merger.py:_run_integration_gates()` lines 934-938 — builds retry_ctx inline when gate fails
2. `engine.py:_recover_integration_e2e_failed()` lines 1040-1044 — rebuilds from stored e2e_output if retry_ctx wasn't set

Both produce:
```
Integration e2e tests failed after merging main into your branch.
Fix the failing tests so they pass.

E2E test output (last 2000 chars):
<raw test runner output>

Original scope: <full scope from planning>
```

### Profile system integration

`profile.parse_test_results()` already exists in the ABC (core) with a web module implementation for Playwright's `✓/✗` list reporter format. However, the gate output uses Playwright's **summary format** (`N failed` + `[browser] › file:line › test name`), which is different. The retry context parser handles the summary format and lives in core — it uses generic regex patterns (`\d+ failed`, `\d+ passed`, indented `[.*] ›` lines) that work across test runners.

## New Flow

```
Agent done → merge queue → E2E gate runs → FAIL
  → _recover_integration_e2e_failed()
    → _build_gate_retry_context(change, wt_path, e2e_output)
      → git log --oneline main..HEAD  (what agent built)
      → git diff --stat main..HEAD    (files changed)
      → parse test results            (pass/fail/flaky counts)
      → format structured prompt
    → resume_change() → set-loop start <enriched_ctx>
```

## Retry Prompt Structure

```
Integration e2e tests failed after merging main into your branch. Fix the failing tests so they pass.

## Your Previous Work

You implemented this change and it's all committed in your working tree. Here's what you built:

### Commits
<git log --oneline main..HEAD>

### Files Changed
<git diff --stat main..HEAD>

## Test Results

**30 passed, 9 failed, 2 flaky** out of 53 tests.

### Failing Tests
- [chromium] tests/e2e/journeys/purchase-flow.spec.ts:61 › 2.3 complete 3-step checkout
- [chromium] tests/e2e/journeys/promotion-stacking.spec.ts:20 › 4.1 apply valid coupon
...

### Test Output (last 2000 chars)
<raw output for error details>

## Original Scope
<scope — kept for reference but agent should focus on fixing failures, not reimplementing>
```

## Implementation

### `_build_gate_retry_context()` — new helper in engine.py

```python
def _build_gate_retry_context(
    change: ChangeState, wt_path: str, e2e_output: str
) -> str:
```

1. Run `git log --oneline main..HEAD` in wt_path (capped at 30 lines)
2. Run `git diff --stat main..HEAD` in wt_path (capped at 50 lines)
3. Parse e2e_output for pass/fail/flaky counts and failing test names
4. Assemble structured prompt

### Test result parsing

Use regex on Playwright output:
- `(\d+) passed` / `(\d+) failed` / `(\d+) flaky` / `(\d+) did not run`
- Failing test lines match: `^\s+\[.*\] › (.+)$`

### E2E output truncation

Currently hardcoded to last 2000 chars in `_run_integration_gates()`. Keep this but add the structured summary above it so the agent has both the overview and the raw details.

## Dual-path consolidation

Both merger.py and engine.py currently build retry_ctx inline. After this change, both call the same `_build_gate_retry_context()` helper, ensuring consistent prompt format regardless of which code path triggers the retry.

```
merger.py:_run_integration_gates()     ─┐
                                        ├─→ _build_gate_retry_context(change, wt_path, e2e_output)
engine.py:_recover_integration_e2e_failed() ─┘
```

## Edge Cases

- **No commits beyond main**: Shouldn't happen (agent was "done"), but if so, skip "Previous Work" section entirely
- **Git commands fail**: Fall back to current behavior (raw output + scope)
- **Very long git log**: Cap at 30 commits, add "... and N more"
- **Non-Playwright test runners**: `_parse_e2e_summary()` regex is generic enough for most runners (`N failed`, `N passed`). If a project type uses a completely different format, the parsed section will be empty and the raw output still provides details

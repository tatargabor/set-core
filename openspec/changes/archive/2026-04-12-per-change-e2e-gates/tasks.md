# Tasks

## 1. Remove acceptance-tests pattern from planner

- [x] 1.1 In `lib/set_orch/templates.py`, delete the "Acceptance test change (REQUIRED)" section (lines 371-428 including the PHASE 0/1/2 methodology block and `{acceptance_test_extra_rules}` placeholder)
- [x] 1.2 In `lib/set_orch/templates.py`, strengthen the "Test-per-change requirement" section (lines 366-369) to explicitly require E2E tests per change: each change that adds routes/features MUST include E2E tests in `tests/e2e/<change-name>.spec.ts`, and the gate runs ALL tests in the directory (not just new ones)
- [x] 1.3 Remove the `acceptance_test_extra_rules` injection logic from the `planning_rules()` function (~lines 479-486) since the methodology is no longer injected into a single final change

## 2. Move test methodology to per-change injection

- [x] 2.1 In `lib/set_orch/profile_types.py`, rename `acceptance_test_methodology()` to `e2e_test_methodology()` in the ABC
- [x] 2.2 In `modules/web/set_project_web/project_type.py`, rename `acceptance_test_methodology()` to `e2e_test_methodology()` and update content for per-change use (remove "cross-feature journey" framing, keep Playwright-specific rules like serial steps, browser context, locators)
- [x] 2.3 Update all callers of `acceptance_test_methodology()` to use the new name

## 3. Default max_parallel to 1

- [x] 3.1 In `lib/set_orch/engine.py`, change `max_parallel: int = 3` to `max_parallel: int = 1` with comment that >1 is experimental

## 4. Python-side test failure classification in gate

- [x] 4.1 Add `_classify_test_failures(wt_path, e2e_output)` helper in `lib/set_orch/engine.py` — runs `git diff --name-only main..HEAD -- tests/e2e/` to get THIS change's new test files, then cross-references with `_parse_e2e_summary()` failing test list. Returns `{own_test_failures: [...], regression_failures: [...], own_test_files: [...]}`
- [x] 4.2 Update `_build_gate_retry_context()` to call `_classify_test_failures()` and structure the retry prompt with two sections: "Your Test Failures" (fix your test or your app code) and "Regression Failures" (your change broke a previously-passing test — fix your app code, don't touch the old test)
- [x] 4.3 In `lib/set_orch/merger.py` `_run_integration_gates()`, pass the same classification when building retry context inline

## 5. Make retry limit configurable and fix exhaustion flow

- [x] 5.1 In `lib/set_orch/engine.py` Directives, add `e2e_retry_limit: int = 3` (was hardcoded 2 in merger.py). Parse from config `e2e_retry_limit`
- [x] 5.2 In `lib/set_orch/merger.py` `_run_integration_gates()`, accept `e2e_retry_limit` param, replace hardcoded `2` with it. Pass from engine via directives
- [x] 5.3 Fix exhaustion: when retry limit reached, set status to `integration-failed` (not fall-through that leaves ambiguous state). Clear from merge queue explicitly. This prevents the infinite loop: merge-blocked → recover → done → gate → fail → merge-blocked
- [x] 5.4 Reset `integration_e2e_retry_count` in `resume_change()` alongside existing `merge_retry_count` reset — prevents stale counter from previous sessions (ISS-002 root cause)

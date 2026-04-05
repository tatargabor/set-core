## 1. Dispatcher: scope E2E narrative post-processing

- [x] 1.1 In `_build_input_content()` (`lib/set_orch/dispatcher.py`), BEFORE writing the `## Required Tests` section: if test_plan_entries exist, scan the `scope` text for narrative E2E descriptions (patterns: `E2E:`, `tests/e2e/`, `spec.ts`) and replace the matching line(s) with: `E2E: See "Required Tests" section below — that is the authoritative and complete test list.`. Use `re.sub(r'E2E:.*?(?=\n\n|\n[A-Z]|\Z)', replacement, scope, flags=re.DOTALL)`. This prevents the agent from seeing conflicting test guidance between scope narrative and Required Tests.
- [x] 1.2 If no test_plan_entries exist, leave scope unchanged (backward compat).

## 2. Dispatcher: strengthen Required Tests section

- [x] 2.1 In `_build_input_content()` (`lib/set_orch/dispatcher.py:1111`), update the `## Required Tests` header and preamble to: `## Required Tests (MANDATORY — coverage gate will block if incomplete)\nYou MUST write tests for ALL scenarios below. This list takes priority over any narrative test descriptions.\nName each test with the REQ-* ID prefix.\nMinimum test count: {len(entries)} (coverage gate blocks below {threshold}%).`. Read threshold from state extras directives (default 80).
- [x] 2.2 After the entry list, add summary: `\nTotal: {len(entries)} required test scenarios. The integration gate verifies coverage before allowing merge.`

## 3. Coverage gate enforcement in merger

- [x] 3.1 In `_run_integration_gates()` (`lib/set_orch/merger.py`), after the E2E gate passes (after Phase 2 own tests pass): add a coverage check block. Load test-plan.json from digest dir (detect via `SetRuntime().digest_dir` with fallback to `set/orchestration/digest`). Get the change's requirements from state. If both exist AND `change.change_type == "feature"`, proceed with coverage check.
- [x] 3.2 Parse the Phase 2 (own) E2E output using `profile.parse_test_results()` to get `{(file, test_name): "pass"|"fail"}`. Load test plan entries filtered by change requirements. Call `build_test_coverage()` then `validate_coverage()` from `test_coverage.py`.
- [x] 3.3 Read `e2e_coverage_threshold` from `state.extras.get("directives", {}).get("e2e_coverage_threshold", 0.8)`. If `coverage.coverage_pct / 100 < threshold`, gate fails.
- [x] 3.4 On coverage failure: build retry context: `"E2E tests pass but coverage is insufficient ({pct:.0f}% vs {threshold*100:.0f}% required).\n\nMissing test scenarios:\n{missing_list}\n\nYour spec files: {own_specs}\nWrite tests for the missing scenarios and commit."`. Set status to `"integration-coverage-failed"`. Increment `integration_e2e_retry_count`. Return False.
- [x] 3.5 On coverage pass: `update_change_field(..., "coverage_check_result", "pass")` and `update_change_field(..., "coverage_pct", coverage.coverage_pct)`. Log info.
- [x] 3.6 Skip coverage check (log reason) when: `e2e_coverage_threshold == 0.0`, or test-plan.json doesn't exist, or change_type not in `("feature",)`, or change has no requirements.

## 4. Configurable threshold directive

- [x] 4.1 Add `e2e_coverage_threshold: float = 0.8` to `Directives` dataclass (`lib/set_orch/engine.py`). Parse from raw directives dict in `_parse_directives()`: `d.e2e_coverage_threshold = float(raw.get("e2e_coverage_threshold", 0.8))`.

## 5. Engine: integration-coverage-failed status handling

- [x] 5.1 In `_recover_integration_e2e_failed()` (`lib/set_orch/engine.py`), add `"integration-coverage-failed"` to the status check alongside `"integration-e2e-failed"`. Both trigger the same redispatch-to-agent recovery path.

## 6. Planner: validate test load per change

- [x] 6.1 In `validate_plan()` (`lib/set_orch/planner.py`), add a post-validation step: for each change with requirements, look up test-plan.json entries and sum `min_tests`. If total > 40, log warning: `"Change {name} has {total} required tests ({n} REQs) — consider splitting"`. This is advisory, not blocking.
- [x] 6.2 For the test load check, `validate_plan()` already receives `digest_dir` parameter.

## 7. Planner: domain-level test plan context (best-effort LLM hint)

- [x] 7.1 Create `_build_test_plan_context(digest_dir: str, requirement_ids: list[str]) -> str` in `lib/set_orch/planner.py`. Load test-plan.json, filter by requirement IDs. Format as: `\n## E2E Test Expectations\nThe following {n} test scenarios are required for the requirements assigned to this change domain:\n{entries}\nEach change MUST include E2E tasks covering its assigned scenarios. Do NOT collapse into narrative.`. Return empty string if no plan or no entries.
- [x] 7.2 In `_decompose_single_domain()` (`lib/set_orch/planner.py`): add `test_plan_context` parameter, inject into design_context for the prompt.
- [x] 7.3 Thread `digest_dir` through: `_phase2_parallel_decompose()` → `_decompose_single_domain()`. Both engine.py replan calls and planner.py main pipeline pass digest_dir.

## 8. Tests

- [ ] 8.1 Unit test scope post-processing: scope with `E2E: cold visit...` + test_plan_entries → E2E line replaced with reference. Scope without E2E → unchanged. No entries → unchanged. (`tests/unit/test_dispatcher.py`)
- [ ] 8.2 Unit test Required Tests header: verify MANDATORY language, count, threshold in output. (`tests/unit/test_dispatcher.py`)
- [ ] 8.3 Unit test coverage gate: mock E2E pass + 50% coverage + feature type → gate fails with retry context listing missing REQs. Mock E2E pass + 90% coverage → gate passes. Non-feature → skip. No test-plan → skip. Threshold 0.0 → skip. (`tests/unit/test_merger.py`)
- [ ] 8.4 Unit test `_build_test_plan_context()`: matching entries → formatted, no entries → empty, no file → empty. (`tests/unit/test_planner.py`)
- [ ] 8.5 Unit test Directives: `e2e_coverage_threshold` from yaml → parsed, missing → 0.8 default. (`tests/unit/test_engine.py`)

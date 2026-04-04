# Tasks: ac-test-coverage-binding

## 1. Test Plan Generator

- [ ] 1.1 Add `generate_test_plan(requirements_json: Path, output_path: Path) -> dict` to `lib/set_orch/test_coverage.py` — reads `requirements.json`, extracts scenarios via `parse_scenarios()`, classifies risk, writes `test-plan.json`. Log each step: requirements loaded, scenarios parsed, risk classified, plan written. [REQ: test-plan-generation-from-digest-scenarios]
- [ ] 1.2 Add `classify_test_risk(scenario: DigestScenario, requirement: dict) -> str` to `ProjectType` ABC in `lib/set_orch/profile_types.py` — default returns `"LOW"`. Core provides risk→min_tests mapping: `{"HIGH": 3, "MEDIUM": 2, "LOW": 1}`. [REQ: istqb-risk-classification-via-profile-system]
- [ ] 1.2b Implement `classify_test_risk()` in `WebProjectType` (`modules/web/set_project_web/project_type.py`) — domain-first lookup (`DOMAIN_RISK = {"auth": "HIGH", "payment": "HIGH", "admin": "HIGH", "forms": "MEDIUM", "navigation": "MEDIUM", "search": "MEDIUM"}`), keyword fallback (`KEYWORD_HIGH = {"delete", "password", "token", "checkout", "security", "mutation"}`, `KEYWORD_MEDIUM = {"submit", "validate", "filter", "sort", "edit", "update"}`). Log classification decision per scenario. [REQ: istqb-risk-classification-via-profile-system]
- [ ] 1.3 Define `test-plan.json` schema as dataclass `TestPlanEntry` in `lib/set_orch/test_coverage.py` — fields: `req_id`, `scenario_slug`, `scenario_name`, `risk`, `min_tests`, `categories: list[str]`. Add `TestPlan` container with `entries: list[TestPlanEntry]`, `non_testable: list[str]`, `generated_at: str`. [REQ: test-plan-generation-from-digest-scenarios]
- [ ] 1.4 Hook `generate_test_plan()` into digest completion — call from `digest.py` after `requirements.json` is written. If digest dir has no scenarios, skip with info log "No testable scenarios found, skipping test plan generation". [REQ: test-plan-generation-from-digest-scenarios]

## 2. Dispatch Integration

- [ ] 2.1 Add `_load_test_plan(digest_dir: Path, change_req_ids: list[str]) -> list[TestPlanEntry]` to `lib/set_orch/dispatcher.py` — loads `test-plan.json`, filters entries by change's requirement IDs. Log: "Loaded N test plan entries for change X (M requirements)". [REQ: req-id-naming-convention-in-test-names]
- [ ] 2.2 Add `## Required Tests` section to `_build_input_content()` in `lib/set_orch/dispatcher.py` — format each entry as `- REQ-XXX: scenario_name [RISK] - N test(s) (categories)`. Include naming instruction: "Name each test with the REQ-* ID prefix". If no plan exists, skip section silently. [REQ: req-id-naming-convention-in-test-names]

## 3. Deterministic Coverage Matcher

- [ ] 3.1 Add `extract_req_ids(test_name: str) -> list[str]` to `lib/set_orch/test_coverage.py` — regex `REQ-[A-Z]+-\d+` extraction from test name string. Returns list (a test may cover multiple REQs). [REQ: deterministic-ac-to-test-coverage-matching]
- [ ] 3.2 Modify `build_test_coverage()` in `lib/set_orch/test_coverage.py` — try REQ-ID extraction first, fall back to fuzzy match. Log per-test: "Bound REQ-HOME-001 (deterministic)" or "Unbound test (no REQ-ID): test_name, trying fuzzy". [REQ: deterministic-ac-to-test-coverage-matching]
- [ ] 3.3 Add `unbound_tests: list[str]` field to `TestCoverage` dataclass — tracks test names without REQ-IDs. Dashboard can show these as warnings. [REQ: deterministic-ac-to-test-coverage-matching]

## 4. Post-Gate Coverage Validation

- [ ] 4.1 Add `validate_coverage(test_plan: TestPlan, coverage: TestCoverage) -> CoverageValidation` to `lib/set_orch/test_coverage.py` — compare expected entries vs actual results. Return per-entry: `{req_id, expected_min, actual_count, status: "complete"|"partial"|"missing"}`. Log summary: "Coverage validation: 8/10 complete, 1 partial (REQ-CONTACT-001: 1/2), 1 missing (REQ-ADMIN-001)". [REQ: post-gate-coverage-validation]
- [ ] 4.2 Define `CoverageValidation` dataclass — fields: `entries: list[CoverageValidationEntry]`, `complete_count`, `partial_count`, `missing_count`, `validated_at`. [REQ: post-gate-coverage-validation]
- [ ] 4.3 Hook `validate_coverage()` into post-E2E gate flow — call after `build_test_coverage()` succeeds. Store validation result in `state.extras["coverage_validation"]`. Log summary. [REQ: post-gate-coverage-validation]

## 5. E2E Methodology Update

- [ ] 5.1 Update `WebProjectType.e2e_test_methodology()` in `modules/web/set_project_web/project_type.py` — add mandatory naming rule: "TEST NAMING: Each test MUST include the REQ-* ID prefix. Format: test('REQ-XXX: description', ...)". Place alongside existing framework rules. [REQ: e2e-methodology-includes-req-id-naming-rule]

## 6. Tests

- [ ] 6.1 Unit test `generate_test_plan()` — input: mock requirements.json with 3 requirements (HIGH/MEDIUM/LOW), verify output entries, risk classification, min_tests, idempotency. [REQ: test-plan-generation-from-digest-scenarios]
- [ ] 6.2 Unit test `classify_test_risk()` — verify core default (LOW), web domain lookup, web keyword fallback, edge cases (multiple keywords, unknown domain). [REQ: istqb-risk-classification-via-profile-system]
- [ ] 6.3 Unit test `extract_req_ids()` — verify regex extraction, multiple IDs, no ID, malformed IDs. [REQ: deterministic-ac-to-test-coverage-matching]
- [ ] 6.4 Unit test `build_test_coverage()` with REQ-ID binding — verify deterministic match takes priority over fuzzy, fallback works, unbound_tests populated. [REQ: deterministic-ac-to-test-coverage-matching]
- [ ] 6.5 Unit test `validate_coverage()` — verify complete/partial/missing detection, summary stats. [REQ: post-gate-coverage-validation]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN digest completes and requirements.json exists THEN test-plan.json is generated with entries per scenario [REQ: test-plan-generation-from-digest-scenarios, scenario: test-plan-generated-after-digest]
- [ ] AC-2: WHEN a requirement has no WHEN/THEN scenarios THEN it is marked non_testable [REQ: test-plan-generation-from-digest-scenarios, scenario: requirement-with-no-when-then-scenarios]
- [ ] AC-3: WHEN generate_test_plan() is called multiple times THEN output is identical [REQ: test-plan-generation-from-digest-scenarios, scenario: test-plan-is-idempotent]
- [ ] AC-4: WHEN no profile override exists THEN all scenarios classified LOW, min_tests=1 [REQ: istqb-risk-classification-via-profile-system, scenario: core-default-risk-classification]
- [ ] AC-5: WHEN web module and domain/keywords match HIGH THEN risk=HIGH, min_tests=3 [REQ: istqb-risk-classification-via-profile-system, scenario: web-module-high-risk-classification]
- [ ] AC-6: WHEN web module and domain/keywords match MEDIUM THEN risk=MEDIUM, min_tests=2 [REQ: istqb-risk-classification-via-profile-system, scenario: web-module-medium-risk-classification]
- [ ] AC-6b: WHEN web module and no keywords match THEN risk=LOW, min_tests=1 [REQ: istqb-risk-classification-via-profile-system, scenario: web-module-low-risk-classification]
- [ ] AC-7: WHEN _build_input_content runs with test-plan.json THEN input.md includes ## Required Tests section [REQ: req-id-naming-convention-in-test-names, scenario: dispatch-includes-required-test-names]
- [ ] AC-8: WHEN test-plan.json does not exist THEN dispatch proceeds without error [REQ: req-id-naming-convention-in-test-names, scenario: no-test-plan-available]
- [ ] AC-9: WHEN test name contains REQ-HOME-001 THEN it is bound deterministically [REQ: deterministic-ac-to-test-coverage-matching, scenario: req-id-extracted-from-test-name]
- [ ] AC-10: WHEN test name has no REQ-ID THEN fuzzy fallback used with warning log [REQ: deterministic-ac-to-test-coverage-matching, scenario: test-without-req-id-falls-back-to-fuzzy-match]
- [ ] AC-11: WHEN multiple tests share same REQ-ID THEN all bound, aggregate result [REQ: deterministic-ac-to-test-coverage-matching, scenario: multiple-tests-for-same-req-id]
- [ ] AC-12: WHEN all expected REQ-IDs have min_tests passing THEN coverage=complete [REQ: post-gate-coverage-validation, scenario: full-coverage-achieved]
- [ ] AC-13: WHEN expected REQ-IDs missing from results THEN warning logged, non-blocking [REQ: post-gate-coverage-validation, scenario: partial-coverage-missing-req-ids]
- [ ] AC-14: WHEN REQ-ID has fewer tests than min_tests THEN warning logged, still counted [REQ: post-gate-coverage-validation, scenario: partial-coverage-insufficient-test-count]
- [ ] AC-15: WHEN Required Tests section generated THEN each entry has format `- REQ-XXX: name [RISK] - N test(s)` and includes naming instruction example [REQ: req-id-naming-convention-in-test-names, scenario: required-tests-section-format]
- [ ] AC-16: WHEN e2e_test_methodology() called THEN includes REQ-ID naming rule [REQ: e2e-methodology-includes-req-id-naming-rule, scenario: methodology-text-updated]

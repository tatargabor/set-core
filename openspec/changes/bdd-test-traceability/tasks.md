# Tasks: BDD Test Traceability

## 1. DigestScenario Data Model

- [x] 1.1 Create `DigestScenario` dataclass in `lib/set_orch/test_coverage.py` with fields: name, when, then, slug [REQ: digest-parses-scenarios-from-spec-files]
- [x] 1.2 Add `scenarios: list[DigestScenario]` — populated by parse_scenarios() from spec markdown, added to requirement dict at API level [REQ: digest-parses-scenarios-from-spec-files]
- [x] 1.3 Implement scenario slug generation: kebab-case of name, deduplicate with `-2`/`-3` suffix [REQ: digest-parses-scenarios-from-spec-files]

## 2. Scenario Parsing in Digest

- [x] 2.1 Add `parse_scenarios(section_text: str) -> list[DigestScenario]` function that finds `#### Scenario:` blocks and extracts WHEN/THEN lines [REQ: digest-parses-scenarios-from-spec-files]
- [x] 2.2 Handle multi-line WHEN/THEN with AND continuations — join with "; " [REQ: digest-parses-scenarios-from-spec-files]
- [x] 2.3 Handle specs without WHEN/THEN format — return empty scenarios list, keep acceptance_criteria as-is [REQ: digest-parses-scenarios-from-spec-files]
- [x] 2.4 Call `parse_scenarios()` during digest API response, populate scenarios field per requirement from spec source files [REQ: digest-parses-scenarios-from-spec-files]

## 3. Digest API Extension

- [x] 3.1 Update `get_digest()` in `lib/set_orch/api/orchestration.py` to include scenarios in requirement response [REQ: digest-api-includes-scenarios]
- [x] 3.2 Update TypeScript `DigestReq` interface in `web/src/lib/api.ts` with `scenarios?: DigestScenario[]` type [REQ: digest-api-includes-scenarios]

## 4. TestCoverage Data Model

- [x] 4.1 Create `TestCase` and `TestCoverage` dataclasses in `lib/set_orch/test_coverage.py` [REQ: store-test-coverage-in-state]
- [x] 4.2 Add serialization/deserialization for TestCoverage to/from dict (for state extras JSON storage) [REQ: store-test-coverage-in-state]

## 5. JOURNEY-TEST-PLAN.md Parser

- [x] 5.1 Create `parse_test_plan(plan_path: Path) -> tuple[list[TestCase], list[str]]` function (returns test cases + non-testable REQ IDs) [REQ: parse-journey-test-plan-into-test-cases]
- [x] 5.2 Parse `## REQ-XXX: Title [RISK]` headers — extract req_id and risk level [REQ: parse-journey-test-plan-into-test-cases]
- [x] 5.3 Parse `- [x]`/`- [ ]` checkbox lines — extract category (Happy/Negative/Boundary) and Given/When/Then text [REQ: parse-journey-test-plan-into-test-cases]
- [x] 5.4 Parse `→ file.spec.ts: "test name"` reference lines — extract test_file and test_name [REQ: parse-journey-test-plan-into-test-cases]
- [x] 5.5 Parse `[NON-TESTABLE]` headers — add to non_testable list [REQ: parse-journey-test-plan-into-test-cases]
- [x] 5.6 Handle missing/malformed plan file — return empty result + warning [REQ: parse-journey-test-plan-into-test-cases]

## 6. Test Result Parser — Core ABC + Web Module Implementation

- [x] 6.1 Add `parse_test_results(self, stdout: str) -> dict[tuple[str,str], str]` method to `ProjectType` ABC in `lib/set_orch/profile_types.py` (default: return empty dict) [REQ: parse-e2e-test-results-via-profile]
- [x] 6.2 Implement `parse_test_results()` in `WebProjectType` (`modules/web/`) — Playwright stdout regex: `[✓✗×]\\s+\\d+\\s+([^:]+):\\d+:\\d+\\s+›\\s+(.+?)\\s+\\(` [REQ: parse-e2e-test-results-via-profile]
- [x] 6.3 In coverage builder: call `profile.parse_test_results(stdout)` then match to plan entries by test_file + test_name (case-insensitive, whitespace-tolerant) [REQ: parse-e2e-test-results-via-profile]

## 7. Coverage Calculation and State Storage

- [x] 7.1 Create `build_test_coverage(plan_cases, non_testable, pw_results, digest_reqs) -> TestCoverage` that cross-references everything [REQ: store-test-coverage-in-state]
- [x] 7.2 Compute covered_reqs, uncovered_reqs, non_testable_reqs, coverage_pct [REQ: coverage-gap-detection]
- [x] 7.3 Handle partial coverage: requirement with some scenarios tested counts as covered [REQ: coverage-gap-detection]

## 8. Post-Merge Integration

- [x] 8.1 In `merger.py:merge_change()`, after acceptance-tests change merges, call test coverage parsing pipeline [REQ: store-test-coverage-in-state]
- [x] 8.2 Read JOURNEY-TEST-PLAN.md from project root (on main after merge) [REQ: parse-journey-test-plan-into-test-cases]
- [x] 8.3 Read E2E gate stdout from change state, call `profile.parse_test_results(stdout)` for framework-specific parsing [REQ: parse-e2e-test-results-via-profile]
- [x] 8.4 Store TestCoverage in `state.extras["test_coverage"]` via locked_state [REQ: store-test-coverage-in-state]

## 9. Report.html Test Coverage Section

- [ ] 9.1 Add `TestCoverageData` dataclass to `reporter.py` with fields for template rendering [REQ: report-includes-test-coverage-section]
- [ ] 9.2 Add "Test Coverage" section to report template: coverage bar, summary stats, REQ table [REQ: report-includes-test-coverage-section]
- [ ] 9.3 Table columns: REQ ID, Name, Scenario count, Test count, Pass/Fail, Risk [REQ: report-includes-test-coverage-section]
- [ ] 9.4 Sort: uncovered first (red bg), then failed, then passed [REQ: report-includes-test-coverage-section]
- [ ] 9.5 Handle missing test_coverage — show "No acceptance test data available" [REQ: report-includes-test-coverage-section]

## 10. Web UI — AC Panel Progressive Disclosure Refactor

- [ ] 10.1 Refactor ACPanel in `DigestView.tsx`: Level 1 = domain rows (collapsed by default), each showing domain name, REQ count, coverage fraction, status indicator [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]
- [ ] 10.2 Level 2: on domain click, expand to show REQ rows — REQ ID, title, change/status, scenario count + test fraction, pass/fail indicator. Gap REQs sort first [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]
- [ ] 10.3 Level 3: on REQ click, expand to show scenario rows — name, risk badge (H/M/L), WHEN/THEN text (compact, muted), test status icon [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]
- [ ] 10.4 Level 4: inline with scenario — test file, test name, result, duration (no extra click needed) [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]
- [ ] 10.5 Backward compat: when `scenarios` is empty, fall back to current plain checkbox rendering [REQ: ac-panel-backward-compatible-without-scenarios]

## 11. Web UI — Coverage Data Integration

- [ ] 11.1 Fetch test_coverage from state API (extend existing digest polling or add separate fetch from orchestration state endpoint) [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]
- [ ] 11.2 Match test_coverage entries to digest scenarios by scenario_slug + req_id [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]
- [ ] 11.3 TypeScript types: add `DigestScenario`, `TestCase`, `TestCoverage` interfaces to `api.ts` [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]
- [ ] 11.4 Risk badges: "H" (bg-red-900 text-red-300), "M" (bg-yellow-900 text-yellow-300), "L" (bg-neutral-800 text-neutral-400) — small rounded inline badges [REQ: risk-level-badges-on-scenarios]
- [ ] 11.5 Non-testable REQs: gray "N/T" badge, excluded from coverage percentage [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests]

## 12. Web UI — Coverage Summary Bar

- [ ] 12.1 Add TuiProgress-style coverage summary bar at top of AC panel: "Coverage: 42/47 (89%)" + bar [REQ: coverage-summary-bar-at-top-of-ac-panel]
- [ ] 12.2 Bar color: green >= 90%, yellow >= 70%, red < 70%. Show non-testable count separately [REQ: coverage-summary-bar-at-top-of-ac-panel]
- [ ] 12.3 When no test_coverage data: hide summary bar entirely, show current AC panel unchanged [REQ: coverage-summary-bar-at-top-of-ac-panel]

## 13. Report.html — Test Coverage Section

- [ ] 13.1 Add `TestCoverageData` to `reporter.py` (coverage_pct, covered, total, gaps, non_testable, per_req rows) [REQ: report-includes-test-coverage-section]
- [ ] 13.2 Add "Test Coverage" section to report template after execution table: summary bar + REQ table [REQ: report-includes-test-coverage-section]
- [ ] 13.3 Table columns: REQ ID | Name | Domain | Scenarios | Tests (pass/fail) | Risk [REQ: report-includes-test-coverage-section]
- [ ] 13.4 Sort: gaps first (class `gap-critical`), then failed, then passed [REQ: report-includes-test-coverage-section]
- [ ] 13.5 When no test_coverage: show "No acceptance test data available" [REQ: report-includes-test-coverage-section]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN spec has `#### Scenario:` with WHEN/THEN THEN digest produces DigestScenario objects with name, when, then, slug [REQ: digest-parses-scenarios-from-spec-files, scenario: spec-with-when-then-scenarios]
- [x] AC-2: WHEN spec has no WHEN/THEN format THEN scenarios list is empty AND acceptance_criteria still works [REQ: digest-parses-scenarios-from-spec-files, scenario: spec-without-when-then-format]
- [x] AC-3: WHEN JOURNEY-TEST-PLAN.md has `## REQ-XXX: Title [HIGH]` THEN parser extracts req_id and risk [REQ: parse-journey-test-plan-into-test-cases, scenario: standard-plan-format]
- [ ] AC-4: WHEN profile.parse_test_results() called with Playwright stdout THEN returns {(file, name): result} mapping [REQ: parse-e2e-test-results-via-profile, scenario: profile-provides-test-result-parser]
- [x] AC-5: WHEN plan and parsed results are cross-referenced THEN TestCase.result is populated [REQ: parse-e2e-test-results-via-profile, scenario: match-results-to-plan-entries]
- [ ] AC-6: WHEN acceptance-tests merges THEN test_coverage stored in state.extras [REQ: store-test-coverage-in-state, scenario: post-merge-trigger]
- [ ] AC-7: WHEN AC panel loads THEN Level 1 shows domain rows with coverage fraction, all collapsed [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests, scenario: level-1-domain-rows]
- [ ] AC-8: WHEN user expands a domain THEN Level 2 shows REQ rows with scenario/test counts, gaps first [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests, scenario: level-2-req-rows]
- [ ] AC-9: WHEN user expands a REQ THEN Level 3 shows scenarios with WHEN/THEN + risk badge + test status [REQ: ac-panel-uses-progressive-disclosure-for-scenarios-and-tests, scenario: level-3-scenario-rows]
- [ ] AC-10: WHEN no scenarios exist (old format) THEN AC panel shows plain checkboxes as before [REQ: ac-panel-backward-compatible-without-scenarios, scenario: requirements-with-acceptance-criteria-but-no-scenarios]
- [ ] AC-11: WHEN report generated with test_coverage THEN Test Coverage section shows REQ table with pass/fail [REQ: report-includes-test-coverage-section, scenario: report-with-coverage-data]
- [ ] AC-12: WHEN coverage < 100% THEN gaps highlighted in report (gap-critical) and UI (sort first) [REQ: coverage-gap-detection, scenario: uncovered-requirement]

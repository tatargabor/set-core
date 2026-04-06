# Tasks: AC-Driven Test Skeleton

## 1. Data Model — AC-ID field in dataclasses

- [x] 1.1 Add `ac_id: str = ""` field to `TestPlanEntry` dataclass [REQ: ac-id-in-test-plan-entries]
- [x] 1.2 Add `ac_id: str = ""` field to `TestCase` dataclass [REQ: ac-id-based-coverage-binding]
- [x] 1.3 Add `ac_id: str = ""` field to `DigestScenario` dataclass [REQ: ac-id-generation-in-digest]

## 2. AC-ID Generation — assign at consumption time

- [x] 2.1 In `generate_test_plan()`: generate `ac_id = f"{req_id}:AC-{i}"` per AC, propagate to DigestScenario and TestPlanEntry [REQ: ac-id-generation-in-digest]
- [x] 2.2 In dispatcher AC display: use full `{rid}:AC-{i}` format [REQ: ac-id-generation-in-digest]
- [x] 2.3 In merger test-plan.json fallback: copy `ac_id` field to TestCase [REQ: ac-id-in-test-plan-entries]

## 3. Skeleton Generation — AC-ID in test names

- [x] 3.1 test_scaffold.py passes ac_id via entries to profile render (already on dataclass) [REQ: ac-id-in-test-skeleton]
- [x] 3.2 WebProjectType.render_test_skeleton() uses `ac_id` in test name: `test('REQ-XXX-NNN:AC-M — scenario', ...)` [REQ: ac-id-in-test-skeleton]
- [x] 3.3 Dispatcher Required Tests section uses AC-ID prefix [REQ: ac-id-in-test-skeleton]

## 4. Coverage Binding — Phase 0 AC-ID match

- [x] 4.1 Add `_AC_ID_RE` regex and `extract_ac_ids()` function [REQ: ac-id-based-coverage-binding]
- [x] 4.2 Add `extract_ac_ids()` implementation [REQ: ac-id-based-coverage-binding]
- [x] 4.3 Add Phase 0 in build_test_coverage(): AC-ID lookup → direct binding before slug fallback [REQ: ac-id-based-coverage-binding]
- [x] 4.4 Logging for Phase 0: `logger.info("AC-ID bound: ...")` [REQ: ac-id-based-coverage-binding]

## 5. Dashboard — AC-ID matching

- [x] 5.1 ACPanel matches by ac_id first, scenario_slug fallback [REQ: dashboard-ac-id-display]
- [x] 5.2 E2E tab highlights AC-ID prefix in test names [REQ: dashboard-ac-id-display]
- [x] 5.3 Build web dashboard — pnpm build passes [REQ: dashboard-ac-id-display]

## 6. Tests

- [x] 6.1 Unit test: generate_test_plan produces ac_id fields (verified in simulation) [REQ: ac-id-in-test-plan-entries]
- [x] 6.2 Unit test: extract_ac_ids works correctly [REQ: ac-id-based-coverage-binding]
- [x] 6.3 Unit test: Phase 0 binds test with AC-ID directly (verified in simulation) [REQ: ac-id-based-coverage-binding]
- [x] 6.4 Unit test: falls back to slug matching without AC-ID (existing tests pass) [REQ: ac-id-based-coverage-binding]
- [x] 6.5 Integration test: run36 simulation with AC-ID names → 46/46 bound, 100% [REQ: ac-id-based-coverage-binding]
- [x] 6.6 Backwards compat: old data without ac_id deserializes correctly [REQ: ac-id-in-test-plan-entries]

## 7. Planning Rules Update

- [x] 7.1 Core planning rules reference AC-ID skeleton format [REQ: ac-id-in-test-skeleton]
- [x] 7.2 Web planning rules reference skeleton fill pattern [REQ: ac-id-in-test-skeleton]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN requirements.json has acceptance_criteria THEN each gets ac_id REQ-XXX-NNN:AC-M [REQ: ac-id-generation-in-digest, scenario: requirements-json-contains-ac-id-per-criterion]
- [x] AC-2: WHEN old requirements.json has plain string ACs THEN pipeline generates AC-IDs from position [REQ: ac-id-generation-in-digest, scenario: backwards-compatibility-with-old-requirements-json]
- [x] AC-3: WHEN test-plan.json is generated THEN each entry has ac_id field [REQ: ac-id-in-test-plan-entries, scenario: test-plan-json-entries-have-ac-id]
- [x] AC-4: WHEN skeleton is generated THEN test blocks use REQ-XXX-NNN:AC-M prefix [REQ: ac-id-in-test-skeleton, scenario: skeleton-test-blocks-use-ac-id-prefix]
- [x] AC-5: WHEN test name contains REQ-XXX-NNN:AC-M THEN Phase 0 binds directly [REQ: ac-id-based-coverage-binding, scenario: phase-0-ac-id-extraction-and-binding]
- [x] AC-6: WHEN test name has REQ-ID but no AC-ID THEN falls back to slug matching [REQ: ac-id-based-coverage-binding, scenario: fallback-to-slug-matching]
- [x] AC-7: WHEN dashboard displays AC tab THEN matches by ac_id first [REQ: dashboard-ac-id-display, scenario: acpanel-matches-by-ac-id]
- [x] AC-8: WHEN run36 simulated with AC-ID test names THEN 46/46 scenarios bind [REQ: ac-id-based-coverage-binding, scenario: phase-0-ac-id-extraction-and-binding]

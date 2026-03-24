# Tasks: E2E Coverage Enforcement

## 1. Decompose hints — web profile

- [x] 1.1 In `modules/web/set_project_web/project_type.py` `decompose_hints()`: add hint for CRUD e2e requirements
- [x] 1.2 Add hint for layout consistency

## 2. Planning rules update

- [x] 2.1 In `modules/web/set_project_web/planning_rules.txt`: add CRUD test checklist section after existing e2e section:
  ```
  CRUD E2E test completeness (REQUIRED for feature changes with data mutations):
  - CREATE: fill form with valid data → submit → verify new item appears in list
  - READ: navigate to list → verify items render with correct data
  - UPDATE: click edit → change field → submit → verify change reflected
  - DELETE: click delete → confirm dialog → verify item removed from list
  - VALIDATION: submit with invalid/empty data → verify error messages
  - LAYOUT: verify sidebar/nav present on every page in the route group
  ```

## 3. E2e coverage gate — verifier

- [x] 3.1 In `lib/set_orch/verifier.py`: add `_execute_e2e_coverage_gate()` — scope keyword extraction, assertion pattern scanning, coverage report in extras
- [x] 3.2 Wire `_execute_e2e_coverage_gate` into verify gate pipeline (after test_files, before review)

## 4. Review prompt injection

- [x] 4.1 In `_execute_review_gate` (verifier.py): check for `e2e_coverage_report` in change extras
- [x] 4.2 Inject coverage gaps into review prompt_prefix as ⚠ E2E COVERAGE GAPS section
  ```
  ⚠ E2E COVERAGE GAPS (from automated scan):
  - create: NOT TESTED
  - delete: NOT TESTED
  Treat missing CRUD coverage as CRITICAL — the agent must add tests.
  ```

## 5. Web template rules

- [x] 5.1 In spa `rules/components.md`: added layout consistency rule
- [x] 5.2 In nextjs `rules/ui-conventions.md`: added same layout consistency rule (no components.md in nextjs template)

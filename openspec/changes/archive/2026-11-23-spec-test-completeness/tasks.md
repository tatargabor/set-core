## 1. Web Module — SpecSection Redesign

- [ ] 1.1 Update `spec_sections()` in `modules/web/set_project_web/project_type.py`: replace the `test_strategy` SpecSection (id="test_strategy", required=False, phase=9) with an expanded testing section (id="testing_infrastructure", required=True, phase=7). The new `prompt_hint` SHALL be a structured multi-paragraph guide covering 7 sub-concerns: test credentials, test data/seed strategy, selector contract (data-testid registry), critical user flows, mock/fixture strategy, error code contracts, and **test stories** (narrative user journey descriptions). Include conditional markers (e.g., "If auth is in scope: …", "If 3+ entities: …") so the write-spec LLM adapts depth. The test stories sub-concern SHALL always be prompted — even minimal projects benefit from 1-2 journey narratives. [REQ: testing-section-covers-7-infrastructure-sub-concerns]

- [ ] 1.2 Update `spec_sections()` phase ordering: ensure the new testing section at phase=6 does not conflict with auth_roles (also phase=6). If conflict, place testing at phase=6.5 or reorder auth_roles to phase=6, testing to phase=7. Verify all web sections maintain a logical progression: data_model(3) → seed_catalog(4) → pages_routes(5) → auth_roles(6) → testing(7) → i18n(8) → design_tokens(9). [REQ: testing-section-is-required-for-web-projects]

## 2. Profile Core — Validation Method

- [ ] 2.1 Add `validate_spec_testing(self, spec_content: str) -> list[str]` method to `ProjectType` ABC in `lib/set_orch/profile_types.py` with default no-op (returns empty list). [REQ: pre-decompose-spec-validation]

- [ ] 2.2 Implement `validate_spec_testing()` in `WebProjectType` (`modules/web/set_project_web/project_type.py`). Detection logic: scan spec_content for auth indicators (REQ-AUTH, login, registration, protected routes, roles) → warn if no test credentials (email+password pattern) found. Scan for entity count (### entity headers or Prisma model markers) → warn if 3+ entities and no seed/reset strategy keywords. Scan for real-time indicators (WebSocket, SSE, streaming, real-time) → warn if no mock/fixture keywords. Return list of warning strings. [REQ: pre-decompose-spec-validation]

## 3. Planner Integration — Pre-Decompose Validation + Test-Infra Scoping

- [ ] 3.1 In `build_decomposition_context()` in `lib/set_orch/planner.py`: after loading spec content, call `profile.validate_spec_testing(spec_content)`. Log each warning at WARNING level. If warnings exist, append a `## SPEC COMPLETENESS WARNINGS\n` section to the decompose context so the LLM planner can compensate. [REQ: pre-decompose-spec-validation]

- [ ] 3.2 In `render_flat_prompt()` and/or `render_domain_decompose_prompt()` in `lib/set_orch/templates.py`: extract testing section from spec content using fuzzy header matching (case-insensitive: "E2E Tests", "Testing", "Test Strategy", "Test Infrastructure", "E2E Test Strategy", "Testing Infrastructure", "Test Conventions"). When found, include the extracted text in the planner context alongside the test_infra_context so the LLM can scope `test-infrastructure-setup` specifically. Fall back to current generic behavior when no testing section found. [REQ: spec-driven-test-infrastructure-setup-scoping]

## 4. Write-Spec Skill Enhancement

- [ ] 4.1 Update `.claude/skills/set/write-spec/SKILL.md`: replace the testing section guidance with an expanded flow. The skill SHALL present sub-concerns conditionally based on what was collected in earlier sections. Add detection logic: "If auth_roles section was filled → ask about test users with specific format (email, password, role). If data_model has 3+ entities → ask about seed/reset strategy. If external services mentioned in requirements → ask about mock approach. If 3+ features → ask about shared selector registry." Include example output format showing the 6 subsections. [REQ: write-spec-skill-enhanced-testing-flow]

- [ ] 4.2 Add testing anti-pattern detection to the write-spec skill's anti-pattern section: "Testing section too vague" (no specific flows), "No test credentials for auth project", "No reset strategy for data-heavy project". These are warnings, not blocks. [REQ: conditional-sub-concern-prompting]

## 5. Documentation

- [ ] 5.1 Expand the "E2E Test Expectations" section in `docs/guide/writing-specs.md`: replace the 15-line example with a comprehensive example showing all 7 sub-concerns (test credentials with named accounts, test data strategy with reset approach, selector contract with registry table, critical flows per feature, mock strategy for external services, error code contract, and **test stories** with 2-3 narrative user journey examples). Add a "Without this" callout explaining consequences (reference: set-designer websocket-server-and-brain exhausted at retry=12 due to missing test infra guidance). [REQ: writing-specs-guide-expanded]

## 6. Review Learnings Pipeline Validation

- [ ] 6.1 Add unit test in `tests/` that creates a fixture review-learnings.jsonl with 5 patterns (3 matching "auth" category, 2 matching "database" category), calls `review_learnings_checklist()` with scope categories=["auth", "general"], and asserts the result contains exactly the 3 auth patterns plus any "general" patterns. Verify non-empty output. [REQ: review-learnings-pipeline-unit-tests]

- [ ] 6.2 Add unit test that verifies `_build_input_content()` includes a "Review Learnings" section when `DispatchContext.review_learnings` is populated. Create a minimal DispatchContext with review_learnings="## Learnings\n- Pattern A" and verify the output contains the learnings text. [REQ: review-learnings-pipeline-unit-tests]

- [ ] 6.3 Add unit test that verifies the review gate learnings injection path: create a mock profile with `review_learnings_checklist()` returning test content, verify that `_execute_review_gate()` constructs a prompt containing "REVIEW LEARNINGS" prefix. This may need to mock the LLM call — verify feasibility and document if infeasible. [REQ: review-learnings-pipeline-unit-tests]

- [x] 6.4 ~~Verify review gate LLM actually acts on learnings~~ — COMPLETED during post-run analysis. Result: 16/16 learnings (100%) have matching findings in `review-findings.jsonl`. The LLM reviewer actively checks against learnings. Gap is NOT in recognition but in fix compliance: 2 patterns marked NOT_FIXED (fix caused regression). See design.md Addendum. [REQ: e2e-run-validation-of-testing-section-flow]

NOTE: Full pipeline trace (JSONL → checklist → input.md → review gate → LLM evaluation) was completed across two investigation sessions (2026-05-10). All 5 stages confirmed working. The review_learnings pipeline is validated end-to-end. Remaining tasks 6.1-6.3 are regression guard unit tests.

## 7. Post-Run Learning: set-designer v2 Analysis

- [ ] 7.1 After set-designer v2 run completes: harvest findings via `set-harvest`. Specifically analyze: (a) which changes struggled with test infrastructure (websocket-server-and-brain exhausted at retry=12 — was it test infra related?), (b) what test patterns agents invented that should have been in the spec, (c) whether review learnings influenced agent behavior (compare early vs late change test quality). Document as a findings report. [REQ: e2e-run-validation-of-testing-section-flow]

- [ ] 7.2 Extract test infrastructure patterns from set-designer codebase that agents built organically: scan `tests/e2e/helpers/`, `tools/mock-claude.mjs`, any shared fixtures. Compare against what the spec described vs what agents had to discover. This gap analysis feeds directly into the write-spec prompt_hint content. [REQ: e2e-run-validation-of-testing-section-flow]

- [ ] 7.3 Test decompose with enhanced spec: update the micro-web scaffold spec (`tests/e2e/scaffolds/micro-web/docs/spec.md`) with an enhanced testing section covering appropriate sub-concerns for a 5-page app. Run `set-orch-core digest run` + decompose on it and verify: (a) test-infrastructure-setup scope references specific items, (b) SPEC COMPLETENESS WARNINGS appear (or don't, appropriately). No full E2E run needed — just validate planner output. [REQ: e2e-run-validation-of-testing-section-flow]

## Acceptance Criteria (from spec scenarios)

### testing-section-covers-6-infrastructure-sub-concerns
- [ ] AC-1: WHEN a user runs write-spec on a web project THEN the testing section prompt presents sub-concerns sequentially AND the output contains structured subsections [REQ: testing-section-covers-6-infrastructure-sub-concerns, scenario: web-project-spec-generation-includes-all-sub-concerns]
- [ ] AC-2: WHEN a web project has auth_roles filled THEN test credentials sub-concern asks about test user accounts AND WHEN no auth detected THEN sub-concern is shortened [REQ: testing-section-covers-6-infrastructure-sub-concerns, scenario: sub-concerns-adapt-to-detected-features]

### testing-section-is-required-for-web-projects
- [ ] AC-3: WHEN user says "skip" for testing section THEN skill warns that testing is required AND asks to confirm [REQ: testing-section-is-required-for-web-projects, scenario: user-cannot-skip-testing-section]
- [ ] AC-4: WHEN write-spec iterates sections THEN testing appears after pages_routes and alongside auth_roles [REQ: testing-section-is-required-for-web-projects, scenario: section-appears-at-phase-6]

### conditional-sub-concern-prompting
- [ ] AC-5: WHEN spec has auth_roles content THEN skill asks for test user accounts with email/password/role [REQ: conditional-sub-concern-prompting, scenario: auth-detected-triggers-credential-prompting]
- [ ] AC-6: WHEN spec has data_model with 3+ entities THEN skill asks about test data reset strategy [REQ: conditional-sub-concern-prompting, scenario: data-model-detected-triggers-seed-strategy-prompting]
- [ ] AC-7: WHEN spec mentions external services THEN skill asks about mock strategy [REQ: conditional-sub-concern-prompting, scenario: external-apis-detected-triggers-mock-strategy-prompting]
- [ ] AC-8: WHEN spec describes 3+ pages/features THEN skill asks about shared data-testid registry [REQ: conditional-sub-concern-prompting, scenario: multiple-features-detected-triggers-selector-contract-prompting]
- [ ] AC-9: WHEN web project has 1-2 pages, no auth, no external APIs THEN skill asks only about critical flows and basic credentials [REQ: conditional-sub-concern-prompting, scenario: minimal-project-gets-shortened-flow]

### pre-decompose-spec-validation
- [ ] AC-10: WHEN spec has auth requirements but no test credentials THEN validation returns warning [REQ: pre-decompose-spec-validation, scenario: auth-without-test-credentials]
- [ ] AC-11: WHEN spec has 3+ entities but no seed strategy THEN validation returns warning [REQ: pre-decompose-spec-validation, scenario: data-model-without-seed-strategy]
- [ ] AC-12: WHEN spec has real-time features but no mock strategy THEN validation returns warning [REQ: pre-decompose-spec-validation, scenario: real-time-features-without-mock-strategy]
- [ ] AC-13: WHEN build_decomposition_context() runs THEN it calls validate_spec_testing() and logs warnings [REQ: pre-decompose-spec-validation, scenario: planner-logs-warnings-before-decompose]
- [ ] AC-14: WHEN spec has no auth, <3 entities, no real-time THEN validate_spec_testing() returns empty list [REQ: pre-decompose-spec-validation, scenario: no-false-positives-for-simple-projects]

### spec-driven-test-infrastructure-setup-scoping
- [ ] AC-15: WHEN spec has testing section describing fixtures THEN test-infra-setup scope references specific items [REQ: spec-driven-test-infrastructure-setup-scoping, scenario: spec-describes-test-infrastructure]
- [ ] AC-16: WHEN spec has no testing section THEN test-infra-setup uses current generic scope [REQ: spec-driven-test-infrastructure-setup-scoping, scenario: spec-has-no-testing-section]
- [ ] AC-17: WHEN spec uses variant headers (E2E Tests, Testing, Test Strategy, etc.) THEN planner recognizes and extracts the section [REQ: spec-driven-test-infrastructure-setup-scoping, scenario: testing-section-extracted-by-fuzzy-header-matching]

### test-stories-capture-behavioral-intent
- [ ] AC-18: WHEN feature involves user interaction THEN skill prompts for narrative user journey stories [REQ: test-stories-capture-behavioral-intent, scenario: test-story-for-interactive-feature]
- [ ] AC-19: WHEN test stories are present in spec THEN digest includes them as context for test-plan.json [REQ: test-stories-capture-behavioral-intent, scenario: test-story-informs-test-plan-json]
- [ ] AC-20: WHEN spec describes existing system behavior THEN test stories generate tests that verify expected behavior [REQ: test-stories-capture-behavioral-intent, scenario: test-stories-as-reverse-engineering-input]
- [ ] AC-21: WHEN test story is written THEN it follows narrative format without code or selectors [REQ: test-stories-capture-behavioral-intent, scenario: test-story-format]

### write-spec-skill-enhanced-testing-flow
- [ ] AC-22: WHEN testing section contains only vague text THEN skill warns "Testing section too vague" [REQ: write-spec-skill-enhanced-testing-flow, scenario: testing-anti-patterns-detected]
- [ ] AC-23: WHEN testing section is assembled THEN output contains structured subsections (Test Credentials, Test Data Strategy, Test Stories, etc.) [REQ: write-spec-skill-enhanced-testing-flow, scenario: output-includes-structured-subsections]

### writing-specs-guide-expanded
- [ ] AC-24: WHEN user reads writing-specs guide THEN E2E Test Expectations includes complete example with all 7 sub-concerns [REQ: writing-specs-guide-expanded, scenario: guide-shows-complete-testing-section-example]
- [ ] AC-25: WHEN guide describes testing section THEN it includes "Without this" callout [REQ: writing-specs-guide-expanded, scenario: guide-explains-consequences-of-skipping]

### review-learnings-pipeline-unit-tests
- [ ] AC-26: WHEN review_learnings_checklist() called with fixture JSONL and matching categories THEN returns non-empty checklist [REQ: review-learnings-pipeline-unit-tests, scenario: checklist-returns-entries-from-fixture-jsonl]
- [ ] AC-27: WHEN _build_input_content() called with review_learnings in context THEN output contains learnings section [REQ: review-learnings-pipeline-unit-tests, scenario: input-md-includes-learnings-section]
- [ ] AC-28: WHEN _execute_review_gate() runs with learnings available THEN review prompt includes REVIEW LEARNINGS prefix [REQ: review-learnings-pipeline-unit-tests, scenario: review-gate-prompt-includes-learnings-prefix]

### e2e-run-validation-of-testing-section-flow
- [ ] AC-29: WHEN enhanced spec is decomposed THEN test-infra-setup scope contains specific items from testing section [REQ: e2e-run-validation-of-testing-section-flow, scenario: enhanced-spec-produces-specific-test-infra-setup-scope]
- [ ] AC-30: WHEN agent is dispatched for feature change THEN input.md contains testing infrastructure context from spec [REQ: e2e-run-validation-of-testing-section-flow, scenario: agent-receives-testing-context-in-input-md]

### review-learnings (modified)
- [x] AC-31: ~~WHEN E2E run completes with 2+ merged changes THEN learnings JSONL exists, checklist returns content, input.md has learnings, review gate has prefix~~ — VALIDATED on set-designer v2 run: 16/16 recognition rate, all pipeline stages working [REQ: review-gate-receives-learnings-checklist, scenario: pipeline-validated-end-to-end-on-real-run]
- [ ] AC-32: WHEN test suite runs THEN at least one test verifies checklist output and one verifies input.md inclusion [REQ: review-gate-receives-learnings-checklist, scenario: unit-tests-guard-pipeline-wiring]

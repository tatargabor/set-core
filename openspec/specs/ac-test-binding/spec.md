# Ac Test Binding Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Python-generated test plan from digest scenarios (test-plan.json)
- ISTQB-inspired risk classification (HIGH/MEDIUM/LOW) driving minimum test count
- REQ-ID naming convention enforcement in test names
- Deterministic REQ-ID extraction from Playwright output (regex, not fuzzy)
- Dispatch injects per-change test plan entries into agent input
- Post-gate coverage validation (warning, not blocking)

### Out of scope
- Changing the Playwright runner or gate pipeline structure
- Removing JOURNEY-TEST-PLAN.md (agent still writes it, validated against generated plan)
- Blocking gates on coverage gaps (warning only for now)
- Modifying digest or planning phase logic
- Risk classification via ML or LLM (keyword-based only)

## Requirements

### Requirement: Test plan generation from digest scenarios
The system SHALL generate `test-plan.json` from `requirements.json` after digest completion. Each requirement's `#### Scenario:` blocks with WHEN/THEN format SHALL become test plan entries. The generator SHALL be a Python function — not LLM-authored — ensuring deterministic, auditable output.

#### Scenario: Test plan generated after digest
- **WHEN** digest completes and `requirements.json` exists in the digest directory
- **THEN** `generate_test_plan()` produces `test-plan.json` alongside `requirements.json`
- **AND** each scenario with WHEN/THEN format becomes a test plan entry with fields: `req_id`, `scenario_slug`, `scenario_name`, `risk`, `min_tests`, `categories`

#### Scenario: Requirement with no WHEN/THEN scenarios
- **WHEN** a requirement in `requirements.json` has acceptance criteria but no `#### Scenario:` blocks with WHEN/THEN format
- **THEN** the requirement is marked `non_testable` in the test plan
- **AND** it does not count toward coverage metrics

#### Scenario: Test plan is idempotent
- **WHEN** `generate_test_plan()` is called multiple times on the same `requirements.json`
- **THEN** the output `test-plan.json` is identical each time

### Requirement: ISTQB risk classification via profile system
The test plan generator SHALL classify each scenario by risk level via `profile.classify_test_risk(scenario, requirement)`. Core SHALL define the ABC method with default `LOW`. Modules SHALL override with domain/keyword-specific logic. Risk→min_tests mapping SHALL be in core. Classification SHALL be done in Python — not delegated to LLM.

#### Scenario: Core default risk classification
- **WHEN** no profile override exists (e.g., NullProfile or CoreProfile)
- **THEN** all scenarios are classified as `LOW`
- **AND** `min_tests` is 1 (1 happy)

#### Scenario: Web module HIGH risk classification
- **WHEN** `WebProjectType.classify_test_risk()` is called
- **AND** the requirement domain matches `{"auth", "payment", "admin"}` OR scenario text contains `{"delete", "password", "token", "checkout", "security", "mutation"}`
- **THEN** risk is classified as `HIGH`
- **AND** `min_tests` is 3 (1 happy + 2 negative)
- **AND** `categories` includes `["happy", "negative", "negative"]`

#### Scenario: Web module MEDIUM risk classification
- **WHEN** `WebProjectType.classify_test_risk()` is called
- **AND** the requirement domain matches `{"forms", "navigation", "search"}` OR scenario text contains `{"submit", "validate", "filter", "sort", "edit", "update"}`
- **THEN** risk is classified as `MEDIUM`
- **AND** `min_tests` is 2 (1 happy + 1 negative)
- **AND** `categories` includes `["happy", "negative"]`

#### Scenario: Web module LOW risk classification
- **WHEN** `WebProjectType.classify_test_risk()` is called
- **AND** scenario does not match HIGH or MEDIUM patterns
- **THEN** risk is classified as `LOW`
- **AND** `min_tests` is 1 (1 happy)
- **AND** `categories` includes `["happy"]`

### Requirement: REQ-ID naming convention in test names
The dispatch context SHALL instruct agents to prefix each E2E test name with the corresponding REQ-* ID. The naming convention SHALL be enforced by Python post-execution validation — not by relying on LLM compliance alone.

#### Scenario: Dispatch includes required test names
- **WHEN** `_build_input_content()` builds the agent's `input.md`
- **AND** `test-plan.json` contains entries for the change's requirements
- **THEN** `input.md` includes a `## Required Tests` section listing each expected test with REQ-ID prefix, scenario name, risk level, and minimum test count

#### Scenario: Required Tests section format
- **WHEN** the `## Required Tests` section is generated
- **THEN** each entry follows the format: `- REQ-XXX: <scenario name> [RISK] - <min_tests> test(s) (<categories>)`
- **AND** the section includes: "Name each test with the REQ-* ID prefix. Example: `test('REQ-HOME-001: Hero heading visible', ...)`"

#### Scenario: No test plan available
- **WHEN** `test-plan.json` does not exist for the current orchestration
- **THEN** dispatch proceeds without the `## Required Tests` section
- **AND** no error is raised (backwards compatible)

### Requirement: Deterministic AC-to-test coverage matching
The coverage matcher SHALL extract REQ-* IDs from test names via regex pattern `REQ-[A-Z]+-\d+`, replacing fuzzy text matching as the primary binding mechanism. Fuzzy matching SHALL be kept as fallback for tests without REQ-IDs.

#### Scenario: REQ-ID extracted from test name
- **WHEN** `build_test_coverage()` processes test results
- **AND** a test name contains `REQ-HOME-001`
- **THEN** the test is deterministically bound to requirement `REQ-HOME-001`
- **AND** no fuzzy matching is attempted for this test

#### Scenario: Test without REQ-ID falls back to fuzzy match
- **WHEN** a test name does not contain a `REQ-[A-Z]+-\d+` pattern
- **THEN** the existing fuzzy matching logic is used as fallback
- **AND** a warning is logged: "Unbound test (no REQ-ID): <test_name>"

#### Scenario: Multiple tests for same REQ-ID
- **WHEN** multiple tests contain the same REQ-ID (e.g., `REQ-CONTACT-001: validation` and `REQ-CONTACT-001: success`)
- **THEN** all tests are bound to that requirement
- **AND** coverage shows the aggregate result (pass only if all pass)

### Requirement: Post-gate coverage validation
After E2E gate execution, the system SHALL compare actual test results against `test-plan.json` expected entries. The validation SHALL be performed in Python — not delegated to LLM review.

#### Scenario: Full coverage achieved
- **WHEN** E2E gate passes and `test-plan.json` exists
- **AND** every expected REQ-ID from the test plan has at least `min_tests` passing tests
- **THEN** coverage validation reports "complete"
- **AND** the change's test coverage data reflects 100% scenario coverage

#### Scenario: Partial coverage — missing REQ-IDs
- **WHEN** E2E gate passes but some expected REQ-IDs have no matching tests
- **THEN** coverage validation logs a warning per missing REQ-ID
- **AND** the dashboard shows those scenarios as "no test" (not "fail")
- **AND** the gate result is NOT changed (validation is non-blocking)

#### Scenario: Partial coverage — insufficient test count
- **WHEN** a REQ-ID has tests but fewer than `min_tests` specified in the plan
- **THEN** coverage validation logs a warning: "REQ-XXX: 1/3 tests (expected 3 for HIGH risk)"
- **AND** the test is still counted as covered (warning, not failure)

### Requirement: E2E methodology includes REQ-ID naming rule
The web profile's `e2e_test_methodology()` SHALL include the REQ-ID naming convention so that agents receive it as a framework constraint, not an optional suggestion.

#### Scenario: Methodology text updated
- **WHEN** `WebProjectType.e2e_test_methodology()` is called
- **THEN** the returned text includes: "TEST NAMING: Each test MUST include the REQ-* ID prefix. Format: test('REQ-XXX: description', ...)"
- **AND** the rule appears as a mandatory framework convention alongside other Playwright rules

## ADDED Requirements

## IN SCOPE
- Enhanced SpecSection for testing infrastructure in web module
- Structured prompt_hint guiding spec authors through 7 testing sub-concerns (including test stories)
- Conditional sub-concern prompting based on detected project features
- Profile-driven pre-decompose spec validation with non-blocking warnings
- Spec-driven scoping of test-infrastructure-setup planner change
- Write-spec skill enhanced prompt flow for testing section
- Writing-specs.md guide updated with craftbrew-level testing examples
- Unit tests for validation logic and learnings pipeline wiring

## OUT OF SCOPE
- Changes to the SpecSection dataclass structure in profile_types.py
- New review_learnings features (only validation of existing pipeline)
- Changes to dispatcher test infra injection (get_test_infra_summary)
- Test-plan.json generation or enforcement (covered by e2e-test-enforcement)
- E2E gate logic changes (covered by other active e2e changes)
- Blocking pre-decompose validation (advisory only)

### Requirement: Testing section covers 7 infrastructure sub-concerns
The web module's `spec_sections()` SHALL return a testing section whose `prompt_hint` guides the write-spec skill through 7 sub-concerns: (1) test credentials, (2) test data and seed strategy, (3) selector contract, (4) critical user flows, (5) mock and fixture strategy, (6) error code contracts, (7) test stories — narrative descriptions of user journeys that agents elaborate into concrete tests during implementation.

#### Scenario: Web project spec generation includes all sub-concerns
- **WHEN** a user runs the write-spec skill on a web project
- **THEN** the testing section prompt SHALL present sub-concerns sequentially
- **AND** the output SHALL contain structured subsections for each addressed sub-concern

#### Scenario: Sub-concerns adapt to detected features
- **WHEN** a web project has auth requirements detected (auth_roles section filled)
- **THEN** the test credentials sub-concern SHALL specifically ask about test user accounts
- **AND** when no auth requirements exist, the test credentials sub-concern SHALL be shortened to "No auth detected — skip or describe test users if needed"

### Requirement: Testing section is required for web projects
The testing SpecSection SHALL have `required=True` and `phase=6` for web projects, ensuring it is always prompted and positioned after pages_routes and alongside auth_roles.

#### Scenario: User cannot skip testing section
- **WHEN** a user says "skip" for the testing section during write-spec
- **THEN** the skill SHALL warn that testing infrastructure is required
- **AND** SHALL ask to confirm skip with explanation of consequences

#### Scenario: Section appears at phase 6
- **WHEN** the write-spec skill iterates through sections
- **THEN** the testing section SHALL appear after pages_routes (phase 5) and alongside auth_roles (phase 6)

### Requirement: Conditional sub-concern prompting
The write-spec skill SHALL adapt testing sub-concern depth based on detected project features. Minimal projects get 2-3 questions, complex projects get 5-6.

#### Scenario: Auth detected triggers credential prompting
- **WHEN** the spec has auth_roles content describing user roles
- **THEN** the skill SHALL ask: "What test user accounts should be seeded? Include email, password, and role for each."

#### Scenario: Data model detected triggers seed strategy prompting
- **WHEN** the spec has data_model content with 3+ entities
- **THEN** the skill SHALL ask: "How should test data be reset between tests? (e.g., DB push + re-seed, transaction rollback)"

#### Scenario: External APIs detected triggers mock strategy prompting
- **WHEN** the spec mentions external services (Stripe, email, webhooks, WebSocket)
- **THEN** the skill SHALL ask: "Which external services need mocking in tests? What approach? (e.g., route interception, test API mode)"

#### Scenario: Multiple features detected triggers selector contract prompting
- **WHEN** the spec describes 3+ pages/features
- **THEN** the skill SHALL ask: "Do you want a shared data-testid registry? List critical selectors agents must use consistently."

#### Scenario: Minimal project gets shortened flow
- **WHEN** a web project has 1-2 pages, no auth, no external APIs
- **THEN** the skill SHALL ask only about critical flows, basic test credentials, and test stories
- **AND** SHALL skip mock strategy and selector contract sub-concerns

### Requirement: Test stories capture behavioral intent
The testing section SHALL include a "Test Stories" sub-concern that captures user journey narratives at a higher abstraction level than acceptance criteria. Test stories describe WHAT the user does, WHAT inputs they provide, WHAT they expect to see, and HOW the system should respond — without specifying concrete test code. Agents elaborate these stories into concrete Playwright tests during implementation.

#### Scenario: Test story for interactive feature
- **WHEN** a feature involves user interaction (chat, form, CRUD)
- **THEN** the skill SHALL prompt: "Describe 1-3 key user journeys as stories — what the user does step by step, what they see at each step. These get elaborated into tests during implementation."
- **AND** the output SHALL contain narrative test stories under a `### Test Stories` subsection

#### Scenario: Test story informs test-plan.json
- **WHEN** test stories are present in the spec's testing section
- **THEN** the digest pipeline SHALL include them as context for test-plan.json generation
- **AND** generated test plan entries SHALL reference their source story

#### Scenario: Test stories as reverse engineering input
- **WHEN** a spec describes expected behavior of an existing system (remediation/refactor spec)
- **THEN** test stories SHALL describe how the system SHOULD work
- **AND** agents SHALL generate tests from the stories that verify the expected behavior
- **AND** failing tests indicate the gap between description and reality

#### Scenario: Test story format
- **WHEN** a test story is written
- **THEN** it SHALL follow the format: a short title, then a narrative paragraph describing the user's journey through the feature including inputs provided, expected visual states, and expected system behavior
- **AND** it SHALL NOT contain code, selectors, or implementation details

### Requirement: Pre-decompose spec validation
The profile SHALL provide a `validate_spec_testing(spec_content: str) -> list[str]` method that returns non-blocking warnings when testing context is missing proportional to spec complexity.

#### Scenario: Auth without test credentials
- **WHEN** the spec contains auth-related requirements (REQ-AUTH-*, login, registration, protected routes)
- **AND** the spec does NOT contain test user credentials (email/password for testing)
- **THEN** validation SHALL return a warning: "Spec has auth requirements but no test credentials defined"

#### Scenario: Data model without seed strategy
- **WHEN** the spec contains a data model with 3+ entities
- **AND** the spec does NOT describe test data seeding or reset strategy
- **THEN** validation SHALL return a warning: "Spec has data model with N entities but no test data/seed strategy"

#### Scenario: Real-time features without mock strategy
- **WHEN** the spec mentions WebSocket, real-time, SSE, or streaming features
- **AND** the spec does NOT describe mock or test infrastructure for real-time
- **THEN** validation SHALL return a warning: "Spec has real-time features but no mock/fixture strategy"

#### Scenario: Planner logs warnings before decompose
- **WHEN** `build_decomposition_context()` runs
- **THEN** it SHALL call `profile.validate_spec_testing(spec_content)`
- **AND** log each warning at WARNING level
- **AND** include warnings in the decompose context as "SPEC COMPLETENESS WARNINGS" section

#### Scenario: No false positives for simple projects
- **WHEN** a spec has no auth, fewer than 3 entities, and no real-time features
- **THEN** `validate_spec_testing()` SHALL return an empty list

### Requirement: Spec-driven test-infrastructure-setup scoping
The planner SHALL read the spec's testing section and include specific infrastructure items in the `test-infrastructure-setup` change scope when available.

#### Scenario: Spec describes test infrastructure
- **WHEN** the spec contains a testing section describing fixtures, selectors, or mock approach
- **AND** the planner creates a `test-infrastructure-setup` change
- **THEN** the change scope SHALL reference specific items from the spec (e.g., "create auth fixture with customer1/admin users, shared selectors.ts")

#### Scenario: Spec has no testing section
- **WHEN** the spec does not contain a testing section
- **AND** the planner creates a `test-infrastructure-setup` change
- **THEN** the change scope SHALL use the current generic description (no regression)

#### Scenario: Testing section extracted by fuzzy header matching
- **WHEN** the spec uses header variants ("## E2E Tests", "## Testing", "## Test Strategy", "## Test Infrastructure", "## E2E Test Strategy")
- **THEN** the planner SHALL recognize all variants and extract the section content

### Requirement: Write-spec skill enhanced testing flow
The write-spec SKILL.md SHALL include updated guidance for the testing section with adaptive questioning, output structure, and anti-pattern detection for testing.

#### Scenario: Testing anti-patterns detected
- **WHEN** the testing section contains only "test that everything works" without specific flows
- **THEN** the skill SHALL WARN: "Testing section too vague — specify which user flows and what success looks like"

#### Scenario: Output includes structured subsections
- **WHEN** the testing section is assembled
- **THEN** the output SHALL contain markdown subsections: "### Test Credentials", "### Test Data Strategy", "### Selector Contract", "### Critical Flows", optionally "### Mock Strategy", "### Error Contracts"

### Requirement: Writing-specs guide expanded
The `docs/guide/writing-specs.md` guide SHALL expand the "E2E Test Expectations" section with craftbrew-level examples covering all 6 sub-concerns.

#### Scenario: Guide shows complete testing section example
- **WHEN** a user reads the writing-specs guide
- **THEN** the "E2E Test Expectations" section SHALL include a complete example with test credentials, data strategy, selector registry, critical flows, mock approach, and error contracts

#### Scenario: Guide explains consequences of skipping
- **WHEN** the guide describes the testing section
- **THEN** it SHALL include a "Without this" callout explaining that agents invent test infrastructure ad-hoc, causing cross-change inconsistency

### Requirement: Review learnings pipeline unit tests
The test suite SHALL include unit tests verifying the review_learnings pipeline wiring: JSONL → checklist → dispatcher injection → review gate prefix.

#### Scenario: Checklist returns entries from fixture JSONL
- **WHEN** `review_learnings_checklist()` is called with a fixture JSONL containing 5 patterns
- **AND** scope categories match 3 of those patterns
- **THEN** the method SHALL return a non-empty checklist string containing those 3 patterns

#### Scenario: Input.md includes learnings section
- **WHEN** `_build_input_content()` is called with a DispatchContext that has `review_learnings` populated
- **THEN** the output SHALL contain a "Review Learnings" or equivalent section with the checklist content

#### Scenario: Review gate prompt includes learnings prefix
- **WHEN** `_execute_review_gate()` runs with a learnings checklist available
- **THEN** the review prompt SHALL include the learnings as `prompt_prefix`

### Requirement: E2E run validation of testing section flow
An E2E run SHALL be performed with a spec containing the enhanced testing section to validate that testing context flows through decompose → dispatch → agent implementation.

#### Scenario: Enhanced spec produces specific test-infra-setup scope
- **WHEN** a micro-web or similar spec with full testing section is decomposed
- **THEN** the `test-infrastructure-setup` change scope SHALL contain specific items from the testing section (not generic "set up Playwright")

#### Scenario: Agent receives testing context in input.md
- **WHEN** an agent is dispatched for a feature change
- **THEN** the agent's input.md SHALL contain testing infrastructure context derived from the spec's testing section

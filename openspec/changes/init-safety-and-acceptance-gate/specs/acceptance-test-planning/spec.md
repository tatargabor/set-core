## ADDED Requirements

## IN SCOPE
- Planner prompt directive requiring a final acceptance-tests change
- Generic journey test methodology rules (not project-specific)
- Robustness patterns: isolation, idempotency, state management
- Fix-until-pass loop requirement
- Planner-time journey extraction from spec domains

## OUT OF SCOPE
- New engine gate types or phase-end E2E modifications
- Acceptance test template files shipped with set-core
- Project-specific test content (concrete selectors, URLs, entity names)
- Changes to the merge pipeline or verify gate
- Email delivery testing (not feasible via Playwright)

### Requirement: Planner includes acceptance-tests change
The decompose prompt in `templates.py` SHALL include a directive instructing the planner to always generate a final `acceptance-tests` change that depends on all other changes.

#### Scenario: Standard decomposition with features
- **WHEN** the planner decomposes a spec with 3+ feature changes
- **THEN** the output SHALL include a change named `acceptance-tests` with `type: "test"`
- **AND** `acceptance-tests` SHALL have `depends_on` listing all other change names
- **AND** `acceptance-tests` SHALL be in the last phase

#### Scenario: Small spec with 1-2 changes
- **WHEN** the planner decomposes a spec with fewer than 3 feature changes
- **THEN** `acceptance-tests` SHALL still be included
- **AND** it SHALL depend on all other changes

### Requirement: Planner extracts cross-domain journeys from spec
The planner SHALL analyze the spec's domain structure and identify cross-domain user journeys. These journeys become the scope of the `acceptance-tests` change.

#### Scenario: Domains with data flow between them
- **WHEN** the spec has domains where one domain's output is another's input (e.g., a domain that creates items feeds into a domain that processes them)
- **THEN** the planner SHALL generate a journey covering that data flow end-to-end
- **AND** list it in the `acceptance-tests` scope as a named journey

#### Scenario: Journey naming in scope
- **WHEN** the planner generates the `acceptance-tests` change
- **THEN** the scope SHALL list each journey with a descriptive name and the domains it connects
- **AND** list target test files as `tests/e2e/journey-<name>.spec.ts`

#### Scenario: Actor-crossing journeys
- **WHEN** the spec has multiple user roles that interact with the same entities (e.g., one role creates/manages, another role consumes)
- **THEN** the planner SHALL generate journeys that cross actor boundaries

### Requirement: Journey test methodology rules in directive
The directive SHALL include generic methodology rules that guide the agent to write robust, self-contained journey tests regardless of project type.

#### Scenario: Shared browser context for serial steps
- **WHEN** the directive instructs the agent about serial test patterns
- **THEN** it SHALL specify: use `test.describe.serial()` with a shared `Page` created in `test.beforeAll` via `browser.newContext()` + `newPage()`
- **AND** explain why: each test step builds on the previous step's state (login, cart, checkout are sequential)

#### Scenario: Self-contained journey files
- **WHEN** the directive instructs about test file structure
- **THEN** it SHALL specify: each journey spec file MUST be self-contained — set up its own preconditions in `beforeAll` via API calls, never depend on state from another spec file
- **AND** explain why: Playwright runs spec files in separate workers, cross-file state sharing is unreliable

#### Scenario: Idempotent test design
- **WHEN** the directive instructs about test reliability
- **THEN** it SHALL specify: journey tests MUST be idempotent — running the same test multiple times (retry on failure) SHALL NOT cause false failures
- **AND** patterns: use unique identifiers (e.g., timestamp-based emails), clean up created entities in afterAll, or design assertions that tolerate pre-existing data

#### Scenario: Fresh user per journey when state mutation matters
- **WHEN** the directive instructs about test data isolation
- **THEN** it SHALL specify: if a journey mutates state that would affect other journeys (e.g., uses a one-time resource, creates records that change counters), it MUST create its own test user via the registration API rather than sharing the seed user
- **AND** explain why: prevents coupling between journey execution order

#### Scenario: Seed data usage rules
- **WHEN** the directive instructs about test data
- **THEN** it SHALL specify: read existing seed data (products, categories, config) but never modify the seed file. If additional entities are needed, create them via API in `beforeAll`
- **AND** specify: discover seed data by reading `prisma/seed.ts` or equivalent, not by hardcoding assumptions

#### Scenario: Third-party service handling
- **WHEN** the directive instructs about external integrations
- **THEN** it SHALL specify: if a journey requires a third-party service (payment provider, email service):
  1. Check if test-mode keys exist in `.env`
  2. If yes, use the provider's test mode (e.g., test card tokens)
  3. If no, test the flow up to the external call, then verify via API side-effects (e.g., order created with status pending-payment)
  4. Never skip the journey entirely — test what can be tested

#### Scenario: Cart and session state cleanup
- **WHEN** the directive instructs about browser state management
- **THEN** it SHALL specify: each journey MUST start with a fresh browser context (`browser.newContext()`) to ensure clean cookies/sessions
- **AND** if mid-journey cleanup is needed, use API calls (e.g., clear cart endpoint) rather than relying on UI actions

### Requirement: Fix-until-pass execution loop
The directive SHALL instruct the acceptance-tests agent to iteratively fix and re-run failing tests until all pass.

#### Scenario: Test failure from app bug
- **WHEN** a journey test fails because the application behavior is incorrect
- **THEN** the agent SHALL fix the application code (not the test) and re-run

#### Scenario: Test failure from test bug
- **WHEN** a journey test fails because of a wrong selector, timing issue, or incorrect assertion
- **THEN** the agent SHALL fix the test code and re-run only the failing tests

#### Scenario: Iterative convergence
- **WHEN** the agent enters the fix-until-pass loop
- **THEN** it SHALL re-run only the failed tests (`npx playwright test --grep "<failed test name>"` or `--last-failed`)
- **AND** repeat until all pass or token budget is exhausted
- **AND** if budget exhausted with remaining failures, document what failed and why in a `JOURNEY-TEST-STATUS.md`

### Requirement: Acceptance criteria coverage verification
The agent SHALL verify that journey tests collectively cover all testable acceptance criteria from the spec.

#### Scenario: AC traceability via comments
- **WHEN** the agent writes journey test steps
- **THEN** each test SHALL include a comment referencing which domain and requirement it validates (e.g., `// Validates: <domain> — <requirement summary>`)

#### Scenario: Coverage self-check
- **WHEN** the agent finishes writing all journey tests
- **THEN** it SHALL read the spec's acceptance criteria or requirements list
- **AND** verify each testable AC has at least one journey test step covering it
- **AND** write additional tests for any uncovered ACs

#### Scenario: Non-testable ACs
- **WHEN** an AC cannot be tested via Playwright (e.g., email delivery, background job execution, SEO crawlability)
- **THEN** the agent SHALL document it as non-testable with reason
- **AND** NOT count it as a coverage gap

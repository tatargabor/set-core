# Capability: e2e-test-layering

## Purpose

Guides agents to write tests at the correct abstraction level: backend logic tested independently (fast, no browser), structural E2E for UI presence, and 1-2 functional E2E tests for end-to-end flow validation.

## IN SCOPE
- Planning rule template for three-tier test strategy
- Web-specific rule for backend/frontend test separation
- Guidance for functional E2E test patterns (full flow tests)

## OUT OF SCOPE
- Enforcing test counts or ratios via gates
- Generating test code automatically
- Modifying the verify gate pipeline ordering
- Non-web project type test strategies (future modules)

## ADDED Requirements

### Requirement: TEST-LAYER-RULE — Three-tier test strategy planning rule

A web-specific planning rule template SHALL exist at `modules/web/templates/rules/e2e-test-layering.md` that instructs agents to write tests at three levels: (1) unit/integration tests for backend logic without a browser, (2) structural E2E tests for UI element presence and attributes, (3) 1-2 functional E2E tests per change that exercise the full pipeline from user input through backend processing to UI state update. This rule SHALL deploy to consumer projects via `set-project init --project-type web`.

#### Scenario: Rule deploys to web consumer project
- **WHEN** `set-project init --project-type web` runs
- **THEN** `.claude/rules/e2e-test-layering.md` SHALL exist in the consumer project

#### Scenario: Rule does not deploy to non-web projects
- **WHEN** `set-project init --project-type example` runs
- **THEN** `.claude/rules/e2e-test-layering.md` SHALL NOT exist in the consumer project

### Requirement: TEST-LAYER-SEPARATION — Backend/frontend test separation guidance

The test layering planning rule SHALL instruct agents that when a change introduces both server-side logic (API routes, WS handlers, data processing, external service integration) and UI components, the server-side logic MUST be tested independently via unit or integration tests (vitest/jest, no browser). Functional E2E tests (with browser) SHALL only verify the connection between backend and frontend — not re-test backend logic through the UI.

#### Scenario: Change with backend and frontend
- **WHEN** an agent implements a change that adds a WS message handler AND a chat UI component
- **THEN** the planning rule instructs the agent to write unit tests for the WS handler (message parsing, routing, error handling) without Playwright
- **AND** write 1-2 Playwright tests that verify sending a message through the UI results in the expected response appearing

#### Scenario: Change with frontend only
- **WHEN** an agent implements a change that only modifies UI components (no new backend logic)
- **THEN** the planning rule instructs the agent to write structural E2E tests and 1-2 functional flow tests
- **AND** backend unit tests are not required

### Requirement: TEST-LAYER-FUNCTIONAL — Functional E2E test guidance

The test layering planning rule SHALL define functional E2E tests as tests that exercise a real user flow end-to-end: user performs an action → the system processes it (API call, WS message, subprocess) → the result appears in the UI. The rule SHALL instruct agents to write 1-2 functional tests per change, focusing on the critical happy path. The rule SHALL specify that functional tests may use mock backends (e.g. Playwright `routeWebSocket`, mock API responses) but MUST exercise the full UI interaction chain (click/type → wait for result → verify rendered output).

#### Scenario: Functional E2E test for chat feature
- **WHEN** an agent writes functional E2E tests for a chat feature
- **THEN** at least one test SHALL send a message via the composer, wait for the response to appear, and verify the message content is rendered in the chat panel

#### Scenario: Functional E2E test for preview feature
- **WHEN** an agent writes functional E2E tests for a preview feature
- **THEN** at least one test SHALL trigger a preview update and verify the iframe or preview panel reflects the change

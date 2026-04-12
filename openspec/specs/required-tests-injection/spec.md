# Spec: Required Tests Injection

## AC-1: Narrative E2E descriptions removed from scope
GIVEN a change scope contains narrative E2E text (e.g., "E2E tests/e2e/cart.spec.ts — cold-visit, add product...")
WHEN the dispatcher builds input.md and test plan entries exist for the change
THEN the narrative E2E text is removed or replaced with a pointer to Required Tests

## AC-2: Required Tests section present for all changes with test plan
GIVEN a change has matching entries in test-plan.json (>0 entries for its REQ-IDs)
WHEN the dispatcher builds input.md
THEN input.md contains a "## Required Tests (MANDATORY)" section with all matching entries

## AC-3: No duplicate test guidance
GIVEN a change scope originally contained narrative E2E text
WHEN the scope is processed and Required Tests are appended
THEN the agent sees ONLY the Required Tests section, not both narrative and structured lists

## AC-4: Changes without test plan entries unaffected
GIVEN a change has 0 matching entries in test-plan.json
WHEN the dispatcher builds input.md
THEN no Required Tests section is appended (current behavior preserved)

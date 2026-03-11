## MODIFIED Requirements

### Requirement: Verify gate step order (MODIFIED)
The verify gate SHALL execute quality checks in a fixed order with fail-fast semantics.

#### Scenario: Full gate pipeline (updated order)
- **WHEN** a change completes (Ralph done)
- **THEN** the verify gate SHALL execute in this order:
  1. **Build verification** — run `build` or `build:ci` from package.json. Fail → retry agent with build output.
  2. **Test execution** — run `test_command` if configured. Fail → retry agent with test output.
  3. **E2E tests** — run `e2e_command` if configured. Fail → retry agent with E2E output.
  4. **Test file existence check** — check if diff contains `.test.` or `.spec.` files. Missing → WARNING notification only (non-blocking).
  5. **LLM code review** — if `review_before_merge: true`, run review via configurable model (default: sonnet). CRITICAL severity → retry agent with review feedback.
  6. **OpenSpec verify** — run `/opsx:verify {change_name}` via Claude with max 5 turns. Fail → retry agent with verify output.

#### Scenario: Build failure skips all subsequent gates
- **WHEN** build verification fails
- **THEN** the gate SHALL NOT proceed to test execution, E2E, review, or verify
- **AND** SHALL retry the agent with build error context (saving LLM tokens and test runtime)

#### Scenario: Test failure skips E2E and later gates
- **WHEN** test execution fails
- **THEN** the gate SHALL NOT proceed to E2E, review, or verify

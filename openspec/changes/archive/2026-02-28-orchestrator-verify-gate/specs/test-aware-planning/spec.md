# Test-Aware Planning

Planner scans project test infrastructure and includes test requirements in change scopes.

## Requirements

### TP-1: Test infrastructure detection
- Before plan decomposition, scan the target project for test infrastructure
- Detection checks (all filesystem-based, no LLM):
  - Config files: `vitest.config.*`, `jest.config.*`, `*.test.*` glob count
  - Package.json: `test` script presence, test framework in devDependencies
  - Helper directories: `src/test/`, `__tests__/`, `test/`, `tests/`
  - Helper files: `**/test-helper*`, `**/factory*`, `**/fixtures*`
- Output: structured data with `{framework, config_exists, test_file_count, has_helpers, test_command}`
- Results injected into planner LLM prompt as context

### TP-2: Planner prompt — test requirements in every change
- Add to the plan decomposition system prompt:
  - "Every change scope MUST include specific test requirements"
  - "Tests should cover: happy path, error cases, and security boundaries"
  - "For security-related changes: include tenant isolation tests, auth guard tests"
- The `scope` field in each planned change should end with a test section, e.g.:
  "... Tests: Vitest unit tests for CRUD operations, tenant isolation test ensuring org A cannot access org B data."

### TP-3: Test infrastructure bootstrap
- If detection finds NO test infrastructure (no config, no test files):
  - Add explicit instruction to planner: "The FIRST change MUST be `test-infrastructure-setup`"
  - This change sets up: test framework config, test database, helper utilities, example test
  - ALL other planned changes MUST `depends_on: ["test-infrastructure-setup"]`
- If detection finds test infrastructure EXISTS:
  - Include framework name and patterns in planner context
  - Instruct: "Follow existing test patterns (framework: vitest, pattern: *.test.ts)"

### TP-4: Test context in planner prompt
- Include in the planner prompt context section:
  ```
  Test Infrastructure:
  - Framework: vitest (vitest.config.ts found)
  - Test files: 23 existing (src/**/*.test.ts)
  - Helpers: src/test/helpers.ts, src/test/factories.ts
  - Test command: npm test
  ```
- If no infra: "Test Infrastructure: NONE — first change must set up test framework"

## IN SCOPE
- Auto-detect e2e_command from playwright config and package.json when not explicitly configured
- Mandatory E2E for feature changes when Playwright infrastructure exists
- Integration with profile.detect_e2e_command() as priority source

## OUT OF SCOPE
- Non-Playwright E2E frameworks (Cypress, etc.)
- Changing gate profile defaults
- Modifying explicit e2e_command behavior from orchestration.yaml

### Requirement: E2E gate shall auto-detect command when not configured
When `e2e_command` is empty, the E2E gate SHALL attempt auto-detection in this order: (1) `profile.detect_e2e_command(wt_path)`, (2) package.json script lookup for keys `test:e2e`, `e2e`, or `playwright`, (3) fallback to `npx playwright test` if playwright.config exists.

#### Scenario: Auto-detect from package.json test:e2e script
- **GIVEN** e2e_command is empty (not configured in directives)
- **AND** profile.detect_e2e_command() returns None
- **AND** worktree contains playwright.config.ts
- **AND** package.json has `"scripts": {"test:e2e": "playwright test"}`
- **WHEN** _execute_e2e_gate runs
- **THEN** it SHALL use "npm run test:e2e" as the e2e command
- **AND** SHALL log "E2E command auto-detected from package.json"

#### Scenario: Auto-detect fallback to npx playwright test
- **GIVEN** e2e_command is empty
- **AND** worktree contains playwright.config.ts
- **AND** package.json has no e2e-related script
- **WHEN** _execute_e2e_gate runs
- **THEN** it SHALL use "npx playwright test" as the e2e command

#### Scenario: No Playwright config — skip as before
- **GIVEN** e2e_command is empty
- **AND** worktree has no playwright.config.ts or playwright.config.js
- **WHEN** _execute_e2e_gate runs
- **THEN** it SHALL return GateResult("skipped") as before

### Requirement: Feature changes shall fail when Playwright exists but no tests found
When e2e_command was auto-detected (not explicitly configured), and playwright.config exists, but no E2E test files are found in the worktree diff, the gate SHALL return "fail" with retry context instructing the agent to write E2E tests.

#### Scenario: Playwright config exists but no test files
- **GIVEN** e2e_command was auto-detected (Playwright config exists)
- **AND** change_type is "feature"
- **AND** no files matching *.spec.ts or *.test.ts exist in e2e test directories
- **WHEN** _execute_e2e_gate runs
- **THEN** it SHALL return GateResult("fail")
- **AND** retry_context SHALL include "E2E tests required for feature changes"

#### Scenario: Explicitly configured e2e_command with no tests — skip
- **GIVEN** e2e_command is explicitly set in orchestration.yaml
- **AND** no E2E test files found
- **WHEN** _execute_e2e_gate runs
- **THEN** it SHALL return GateResult("skipped") as before
- **AND** SHALL NOT fail (explicit config = user chose to skip)

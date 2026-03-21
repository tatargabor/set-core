## MODIFIED Requirements

### Requirement: E2E gate performs health check before running Playwright
The verify gate SHALL determine whether Playwright manages its own dev server by checking for a `webServer` block in `playwright.config.ts`/`.js`. When Playwright manages the server, the gate SHALL skip manual health checks and port allocation. When Playwright does NOT manage the server, the existing health check behavior SHALL apply.

#### Scenario: Playwright config has webServer block
- **WHEN** the E2E gate starts for a change
- **AND** `playwright.config.ts` contains a `webServer` configuration block
- **THEN** the gate SHALL NOT perform a manual health check
- **AND** the gate SHALL NOT allocate a random port or set `PW_PORT`
- **AND** the gate SHALL run the `e2e_command` directly, letting Playwright manage the dev server lifecycle

#### Scenario: Playwright config has no webServer block
- **WHEN** the E2E gate starts for a change
- **AND** `playwright.config.ts` does NOT contain a `webServer` configuration block
- **THEN** the gate SHALL perform the health check on the allocated port as before
- **AND** if the health check fails, the gate SHALL skip with output describing the failure

#### Scenario: Dev server does not respond within timeout
- **WHEN** the E2E gate starts for a change
- **AND** no `webServer` block exists in the Playwright config
- **AND** the dev server does not respond within the health check timeout (default 30 seconds)
- **THEN** the E2E gate SHALL skip with a warning: "E2E skipped: dev server not ready after {timeout}s"
- **AND** the E2E result SHALL be set to "skipped" (not "fail")
- **AND** the change SHALL NOT be failed due to the health check timeout

#### Scenario: E2E command not configured
- **WHEN** the verify gate runs for a change without an `e2e_command` configured
- **THEN** the health check probe SHALL NOT run
- **AND** E2E SHALL be skipped as before

#### Scenario: Health check timeout is configurable
- **WHEN** the orchestration configuration includes an `e2e_health_timeout` value
- **THEN** the probe SHALL use that value as the timeout in seconds
- **AND** if not configured, the default SHALL be 30 seconds

### Requirement: E2E test discovery reads Playwright config
The `_count_e2e_tests()` function SHALL determine the test directory from the project's Playwright configuration rather than using a hardcoded path.

#### Scenario: Playwright config specifies testDir
- **WHEN** `playwright.config.ts` contains `testDir: "./e2e"` (or any custom path)
- **THEN** `_count_e2e_tests()` SHALL search for `.spec.ts` and `.spec.js` files in that directory
- **AND** SHALL return the correct count

#### Scenario: Playwright config does not specify testDir
- **WHEN** `playwright.config.ts` exists but does not contain a `testDir` field
- **THEN** `_count_e2e_tests()` SHALL search the Playwright default directory (`tests/`)
- **AND** SHALL also search common conventions: `e2e/`, `tests/e2e/`, `test/e2e/`

#### Scenario: No Playwright config exists
- **WHEN** no `playwright.config.ts` or `playwright.config.js` exists in the worktree
- **THEN** `_count_e2e_tests()` SHALL return 0

### Requirement: E2E gate skip reasons are diagnostic
Every E2E gate skip SHALL include a descriptive `output` field in the GateResult explaining why the gate was skipped.

#### Scenario: Skip due to no e2e_command
- **WHEN** E2E gate skips because `e2e_command` is empty
- **THEN** GateResult output SHALL be "e2e_command not configured"

#### Scenario: Skip due to no Playwright config
- **WHEN** E2E gate skips because no `playwright.config.ts`/`.js` was found
- **THEN** GateResult output SHALL be "no playwright.config.ts/js found in worktree"

#### Scenario: Skip due to no test files
- **WHEN** E2E gate skips because test count is 0
- **THEN** GateResult output SHALL include the directories that were searched (e.g., "no e2e test files found (searched: e2e/, tests/e2e/)")

#### Scenario: Skip due to health check failure (no webServer)
- **WHEN** E2E gate skips because manual health check failed
- **THEN** GateResult output SHALL include the URL that was checked and the timeout

### Requirement: E2E server cleanup matches startup mode
The E2E gate SHALL only attempt manual server cleanup (pkill) when it performed manual server management. When Playwright manages the server via `webServer`, the gate SHALL NOT pkill dev servers.

#### Scenario: Playwright manages server — no cleanup
- **WHEN** E2E tests complete and Playwright managed the dev server via `webServer`
- **THEN** the gate SHALL NOT run pkill commands for dev servers
- **AND** Playwright's own cleanup SHALL handle server shutdown

#### Scenario: Manual server management — cleanup as before
- **WHEN** E2E tests complete and the gate managed the server manually
- **THEN** the gate SHALL pkill the dev server on the allocated port as before

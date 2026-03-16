## ADDED Requirements

### Requirement: E2E gate performs health check before running Playwright
The verify gate SHALL poll the dev server for readiness before executing the E2E command (Playwright). The probe SHALL use the same port assigned via `PW_PORT` and wait for a successful HTTP response before proceeding.

#### Scenario: Dev server responds within timeout
- **WHEN** the E2E gate starts for a change
- **AND** the dev server responds with HTTP 2xx or 3xx within the health check timeout
- **THEN** the E2E command SHALL proceed immediately after the successful health check

#### Scenario: Dev server does not respond within timeout
- **WHEN** the E2E gate starts for a change
- **AND** the dev server does not respond within the health check timeout (default 30 seconds)
- **THEN** the E2E gate SHALL skip with a warning: "E2E skipped: dev server not ready after {timeout}s"
- **AND** the E2E result SHALL be set to "skip-unhealthy" (not "fail")
- **AND** the change SHALL NOT be failed due to the health check timeout

#### Scenario: E2E command not configured
- **WHEN** the verify gate runs for a change without an `e2e_command` configured
- **THEN** the health check probe SHALL NOT run
- **AND** E2E SHALL be skipped as before

#### Scenario: Health check timeout is configurable
- **WHEN** the orchestration configuration includes an `e2e_health_timeout` value
- **THEN** the probe SHALL use that value as the timeout in seconds
- **AND** if not configured, the default SHALL be 30 seconds

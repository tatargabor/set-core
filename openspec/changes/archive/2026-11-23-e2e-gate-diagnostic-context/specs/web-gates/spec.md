# web-gates — Delta Spec (e2e-gate-diagnostic-context)

## MODIFIED Requirements

### Requirement: E2E gate retry context includes webServer log on crash/timeout

When the E2E gate fails without parseable Playwright failure markers, or on webServer timeout, the retry context SHALL include extracted webServer log lines from the combined output. Lines matching the `[WebServer]` prefix SHALL be collected and appended to the retry context under a `## webServer Log` section (last 30 lines max).

If no `[WebServer]` lines are found, the retry context SHALL include the last 50 lines of raw combined output under `## Raw Output (tail)`.

#### Scenario: webServer timeout includes server log
- **WHEN** the E2E gate times out waiting for webServer
- **AND** the combined output contains lines prefixed with `[WebServer]`
- **THEN** the retry context SHALL include a `## webServer Log` section with the last 30 `[WebServer]` lines
- **AND** the existing timeout message SHALL remain as the first paragraph

#### Scenario: Crash without parseable failures includes server log
- **WHEN** the E2E gate fails with non-zero exit code
- **AND** `_extract_e2e_failure_ids()` returns an empty set
- **AND** the combined output contains `[WebServer]` lines
- **THEN** the retry context SHALL include the extracted webServer log

#### Scenario: No webServer lines falls back to raw tail
- **WHEN** the E2E gate fails without parseable failures
- **AND** the combined output contains zero `[WebServer]` lines
- **THEN** the retry context SHALL include the last 50 lines of raw output under `## Raw Output (tail)`

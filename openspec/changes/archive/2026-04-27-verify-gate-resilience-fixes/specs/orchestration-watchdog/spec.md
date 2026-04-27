## ADDED Requirements

### Requirement: Watchdog timeouts configurable and raised to evidence-based values
The watchdog timeouts SHALL be exposed as directives and raised to values that reflect actual observed agent runtime durations.

| Directive | New Default |
|---|---|
| `watchdog_timeout_running` | 1800s (30 min, was 600s) |
| `watchdog_timeout_verifying` | 1200s (20 min, was 300s) |
| `watchdog_timeout_dispatched` | 120s (unchanged) |

The corresponding module-level constants `WATCHDOG_TIMEOUT_RUNNING`, `WATCHDOG_TIMEOUT_VERIFYING`, `WATCHDOG_TIMEOUT_DISPATCHED` SHALL remain as backward-compatible aliases bound to the directive defaults.

#### Scenario: Default verifying timeout absorbs full e2e gate suite
- **WHEN** an agent enters `verifying` state and runs a 24-spec Playwright suite
- **AND** the suite takes 15 min to complete
- **THEN** the watchdog does NOT fire `running but agent dead` because the timeout is 20 min
- **AND** the suite completes normally

#### Scenario: Operator overrides per project
- **WHEN** an operator sets `watchdog_timeout_running: 3600` in `orchestration.yaml`
- **THEN** the watchdog uses 60 min as the running-state timeout for that run

### Requirement: Issue-diagnosed timeout configurable and raised
The issue watchdog's `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS` SHALL be exposed as directive `issue_diagnosed_timeout_secs` and raised from 3600s to 5400s (90 min). The constant SHALL remain as a backward-compatible alias.

#### Scenario: Cross-cutting fix-iss completes within budget
- **WHEN** a complex cross-cutting issue requires ~70 min from `diagnosed` to dispatched fix-iss
- **THEN** the issue watchdog does NOT fire `ISSUE_DIAGNOSED_TIMEOUT` early
- **AND** the fix dispatch completes normally

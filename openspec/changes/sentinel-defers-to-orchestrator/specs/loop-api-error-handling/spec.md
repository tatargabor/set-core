## ADDED Requirements

### Requirement: API error detection
wt-loop SHALL detect Claude API errors (rate limits, server errors, connection failures) by parsing the claude CLI exit code and stderr output after each iteration.

#### Scenario: Rate limit error detected
- **WHEN** claude CLI exits with non-zero code and stderr contains "429", "rate limit", or "overloaded"
- **THEN** wt-loop SHALL classify the error as `api_error` and enter backoff state instead of counting it as a failed iteration

#### Scenario: Server error detected
- **WHEN** claude CLI exits with non-zero code and stderr contains "503", "502", "500", or "internal server error"
- **THEN** wt-loop SHALL classify the error as `api_error` and enter backoff state

#### Scenario: Connection error detected
- **WHEN** claude CLI exits with non-zero code and stderr contains "ECONNRESET", "connection reset", "ETIMEDOUT", or "socket hang up"
- **THEN** wt-loop SHALL classify the error as `api_error` and enter backoff state

#### Scenario: Non-API error passes through
- **WHEN** claude CLI exits with non-zero code and stderr does NOT match any API error pattern
- **THEN** wt-loop SHALL use existing retry logic (2 retries, 30s fixed wait)

### Requirement: Waiting API status
wt-loop SHALL set loop status to `waiting:api` when in API error backoff state. This status MUST be distinct from `stalled` and `running`.

#### Scenario: Status set during backoff
- **WHEN** wt-loop detects an API error and enters backoff
- **THEN** loop-state.json status SHALL be set to `waiting:api`

#### Scenario: Status cleared after recovery
- **WHEN** the next iteration after backoff succeeds (claude CLI exits 0)
- **THEN** loop-state.json status SHALL be reset to `running` and backoff counter SHALL be reset to 0

### Requirement: Exponential backoff
wt-loop SHALL implement exponential backoff for API errors: 30s, 60s, 120s, 240s. After max backoff attempts (10), the loop SHALL set status to `stalled` with reason `api_unavailable`.

#### Scenario: Progressive backoff
- **WHEN** consecutive API errors occur
- **THEN** wait times SHALL double each time: 30s → 60s → 120s → 240s (capped at 240s)

#### Scenario: Max attempts exhausted
- **WHEN** 10 consecutive API error backoffs occur without a successful iteration
- **THEN** wt-loop SHALL set status to `stalled` and log reason as `api_unavailable`

### Requirement: Watchdog recognizes waiting:api
The orchestration watchdog SHALL treat `waiting:api` as a transient non-stall state and SHALL NOT escalate or kill the loop while in this state.

#### Scenario: Watchdog checks loop in waiting:api
- **WHEN** watchdog detects a loop with status `waiting:api`
- **THEN** watchdog SHALL skip stall detection for that loop and log "loop waiting for API recovery"

### Requirement: Sentinel recognizes waiting:api
The sentinel prompt SHALL list `waiting:api` as a Tier 1 (defer) situation — the loop handles API recovery automatically.

#### Scenario: Sentinel observes waiting:api in state
- **WHEN** sentinel poll shows a change's loop in `waiting:api` status
- **THEN** sentinel SHALL take no action — this is transient and self-recovering

## ADDED Requirements

### Requirement: Smoke blocking gate
When `smoke_blocking: true` is set in orchestration directives, smoke tests SHALL block subsequent merges until the current change's smoke is green.

#### Scenario: Smoke blocks next merge
- **WHEN** `smoke_blocking` is `true`
- **AND** a change has status `merged` with smoke pending
- **THEN** the merge lock (flock) SHALL be held through the entire smoke+fix pipeline
- **AND** no other change SHALL be able to merge until the lock is released

#### Scenario: Non-blocking mode (default)
- **WHEN** `smoke_blocking` is `false` (default)
- **THEN** smoke tests SHALL run as before — after merge, non-blocking, results logged but not gating

### Requirement: Health check before smoke
Before running smoke tests, the orchestrator SHALL verify the dev server is responding.

#### Scenario: Server responding
- **WHEN** `merge_change()` runs post-merge smoke
- **AND** `curl -s -o /dev/null -w '%{http_code}' $health_check_url` returns 200 within `smoke_health_check_timeout` seconds
- **THEN** smoke tests SHALL proceed normally

#### Scenario: Server not responding
- **WHEN** the health check fails (no response or non-200 within timeout)
- **THEN** the change status SHALL be set to `smoke_blocked`
- **AND** `smoke_status` SHALL be set to `"blocked"`
- **AND** a critical notification SHALL be sent: "Smoke blocked for {change_name} — no server at {url}"
- **AND** the merge lock SHALL be released

#### Scenario: URL auto-extraction
- **WHEN** `smoke_health_check_url` is empty
- **AND** `smoke_command` contains a URL pattern (e.g., `localhost:3002`)
- **THEN** the health check URL SHALL be extracted from the smoke command
- **AND** used as `http://localhost:{port}`

#### Scenario: Recompile buffer
- **WHEN** health check passes
- **THEN** the orchestrator SHALL wait 5 seconds before running smoke (recompile buffer for HMR/turbopack)

### Requirement: Scoped smoke fix agent
When smoke tests fail, the fix agent SHALL receive change-specific context.

#### Scenario: Scoped fix prompt
- **WHEN** smoke tests fail for change `{name}`
- **THEN** the fix prompt SHALL include:
  - Smoke command and full output (not truncated to 2000 chars)
  - List of files modified by this change (`git diff HEAD~1 --name-only`)
  - Change scope description from state.json
  - Constraint: "MAY ONLY modify files that were part of this change"
  - Constraint: "MUST NOT delete or weaken existing test assertions"

#### Scenario: Fix attempt verification
- **WHEN** the fix agent produces a commit
- **THEN** the orchestrator SHALL run unit tests + build before re-running smoke
- **AND** if unit tests or build fail, `git revert HEAD --no-edit` and count as failed attempt

#### Scenario: Fix succeeds
- **WHEN** the fix agent's changes cause smoke to pass
- **THEN** `smoke_result` SHALL be set to `"fixed"`
- **AND** `smoke_status` SHALL be set to `"done"`
- **AND** a Learning memory SHALL be saved

#### Scenario: Fix retries exhausted
- **WHEN** the fix agent fails `smoke_fix_max_retries` times (default: 3)
- **THEN** the change status SHALL be set to `smoke_failed`
- **AND** `smoke_status` SHALL be set to `"failed"`
- **AND** a critical notification SHALL be sent
- **AND** the merge lock SHALL be released

### Requirement: New orchestration directives for smoke
The orchestrator SHALL parse additional smoke-related directives.

#### Scenario: Directive parsing
- **WHEN** orchestration.yaml or spec brief contains:
  - `smoke_blocking: true|false` (default: false)
  - `smoke_fix_token_budget: N` (default: 500000)
  - `smoke_fix_max_turns: N` (default: 15)
  - `smoke_fix_max_retries: N` (default: 3)
  - `smoke_health_check_url: URL` (default: auto-extract from smoke_command)
  - `smoke_health_check_timeout: N` (default: 30)
- **THEN** these values SHALL be available in state.json directives

#### Scenario: Invalid directive values
- **WHEN** a smoke directive has an invalid value (negative number, non-boolean for blocking)
- **THEN** the default value SHALL be used
- **AND** a warning SHALL be logged

### Requirement: Granular smoke status tracking
State.json SHALL track smoke progress at a granular level.

#### Scenario: Status fields
- **WHEN** a change enters the post-merge smoke pipeline
- **THEN** state.json SHALL include per-change fields:
  - `smoke_status`: "pending" → "checking" → "running" → "fixing" → "done" | "failed" | "blocked"
  - `smoke_fix_attempts`: number of fix attempts made

#### Scenario: Sentinel observability
- **WHEN** a change is in `smoking` state for more than 15 minutes
- **THEN** the sentinel poll SHALL be able to detect this via state.json timestamps

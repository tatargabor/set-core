## Requirements

### Requirement: Local smoke test execution in verify gate
The verify gate SHALL support running smoke/e2e tests locally in the change worktree.

#### Scenario: Smoke command configured
- **WHEN** `smoke_command` directive is non-empty
- **AND** a change passes build verification (Step 2)
- **THEN** the gate SHALL acquire an exclusive lock via `flock --timeout 180 /tmp/wt-smoke-gate.lock`
- **AND** run `timeout {smoke_timeout} bash -c "{smoke_command}"` in the worktree
- **AND** capture exit code and output (truncated to 2000 chars)
- **AND** store `smoke_result` (pass/fail), `smoke_output`, and `gate_smoke_ms` in change state

#### Scenario: Smoke serialization via flock
- **WHEN** multiple changes reach the smoke gate simultaneously
- **THEN** only one smoke test SHALL run at a time (flock serialization)
- **AND** subsequent smoke gates SHALL wait up to 180 seconds for the lock
- **AND** if the lock times out, the gate SHALL log a warning and skip smoke (set `smoke_result` to "skip")
- **RATIONALE** all worktrees share the same database (via `.env` copy); project smoke `globalSetup` may reset+seed the DB; parallel smoke would cause data corruption; also avoids overloading the machine with multiple Playwright+dev server instances

#### Scenario: Smoke command not configured
- **WHEN** `smoke_command` is empty or unset
- **THEN** the gate SHALL skip smoke execution entirely
- **AND** set `smoke_result` to "skip"

#### Scenario: Smoke failure triggers retry
- **WHEN** smoke tests fail
- **AND** `verify_retry_count` < `max_verify_retries`
- **THEN** the gate SHALL increment `verify_retry_count`, set status to `verify-failed`
- **AND** create `retry_context` with: smoke command, smoke output, original scope
- **AND** call `resume_change()` to let the agent fix the failing smoke tests
- **AND** SHALL NOT proceed to LLM review or OpenSpec verify (fail-fast)

#### Scenario: Smoke failure retry exhausted
- **WHEN** smoke tests fail
- **AND** `verify_retry_count` >= `max_verify_retries`
- **THEN** the gate SHALL mark status `failed` and send a critical notification

### Requirement: Deploy smoke test execution after merge
The orchestrator SHALL optionally run smoke tests against a deployed environment after merge.

#### Scenario: Deploy smoke configured
- **WHEN** `deploy_smoke_url` directive is non-empty
- **AND** a change is successfully merged
- **THEN** the orchestrator SHALL poll `{deploy_smoke_url}{deploy_healthcheck}` with `curl -sf` every 10 seconds, max 30 attempts (5 minutes)
- **AND** once healthy, run `SMOKE_BASE_URL={deploy_smoke_url} timeout {smoke_timeout} bash -c "{smoke_command}"` in the project root
- **AND** store `deploy_smoke_result` (pass/fail) in change state

#### Scenario: Deploy smoke not configured
- **WHEN** `deploy_smoke_url` is empty or unset
- **THEN** the orchestrator SHALL skip deploy smoke entirely

#### Scenario: Deploy smoke failure is advisory
- **WHEN** deploy smoke tests fail
- **THEN** the orchestrator SHALL send a warning notification
- **AND** SHALL NOT block other changes or trigger agent retry
- **AND** SHALL NOT revert the merge

#### Scenario: Deploy healthcheck timeout
- **WHEN** the healthcheck does not return 200 within 30 attempts
- **THEN** the orchestrator SHALL log a warning and skip deploy smoke
- **AND** send a notification: "Deploy healthcheck timeout — skipping deploy smoke for {change_name}"

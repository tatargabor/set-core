## ADDED Requirements

### Requirement: Build-fix iterations SHALL NOT consume verify retry budget
When the verify gate detects a build failure and dispatches the agent to fix it, this iteration SHALL NOT increment `verify_retry_count`. The counter SHALL only be incremented when a full verify gate run (test, build, review, scope) completes with a failure result.

#### Scenario: Agent self-heals build error
- **WHEN** verify gate runs build check and build fails (exit code != 0)
- **AND** `verify_retry_count` < `max_verify_retries`
- **THEN** the system SHALL set status to `verify-failed` and dispatch a resume with build-fix retry context
- **AND** the system SHALL NOT increment `verify_retry_count`

#### Scenario: Build-fix agent returns, verify gate runs again
- **WHEN** a resumed agent completes after a build-fix dispatch
- **AND** the verify gate runs the full gate sequence (build → test → review → scope)
- **AND** any gate fails
- **THEN** the system SHALL increment `verify_retry_count` normally

#### Scenario: Build fails repeatedly without self-healing
- **WHEN** build fails and a build-fix resume is dispatched
- **AND** the Ralph loop exhausts its own iteration limit without fixing the build
- **THEN** the Ralph loop SHALL exit with failure
- **AND** the monitor SHALL detect the dead agent and mark the change as failed

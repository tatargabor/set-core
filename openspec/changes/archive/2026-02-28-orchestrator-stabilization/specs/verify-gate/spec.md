## MODIFIED Requirements

### Requirement: Verify gate step order
The verify gate in `handle_change_done()` SHALL execute quality checks in this order: (1) run tests, (2) build verification, (2b) test file existence check, (3) LLM code review, (4) /opsx:verify. Build verification runs before LLM review/verify to catch failures early and save tokens on changes that don't compile.

#### Scenario: Build fails before review
- **WHEN** the build step fails
- **THEN** the LLM review and /opsx:verify steps SHALL be skipped, saving their token cost

#### Scenario: All steps pass
- **WHEN** tests pass, build passes, review passes, and verify passes
- **THEN** the change SHALL proceed to merge

### Requirement: Verify failure retry context
WHEN `/opsx:verify` fails and triggers a retry, the orchestrator SHALL store the verify output in `retry_context` before calling `resume_change()`, so the agent receives specific information about what verify found.

#### Scenario: Verify fails with actionable feedback
- **WHEN** /opsx:verify returns failure with output describing issues
- **THEN** the output SHALL be stored in the change's `retry_context` field AND `resume_change()` SHALL include this context in the task description

### Requirement: Verify retry count tracking
The verify gate SHALL use an integer `verify_retry_count` (not a boolean `verify_retried`) to track retry attempts, with a configurable `max_verify_retries` limit (default: 2).

#### Scenario: Retry count incremented
- **WHEN** any verify gate step fails and triggers a retry
- **THEN** verify_retry_count SHALL be incremented by 1

#### Scenario: Max retries exceeded
- **WHEN** verify_retry_count reaches max_verify_retries
- **THEN** the change SHALL be marked as "failed" with no further retries

## ADDED Requirements

### Requirement: Review retry loop exits on test pass
When the agent loop runs with `done_criteria = "test"`, the loop SHALL exit with status `"done"` when `is_done("test")` returns True. The change then returns to the verification pipeline for re-review.

#### Scenario: Agent fixes issue and tests pass
- **WHEN** the agent applies a security fix during a review retry iteration
- **AND** `_check_test_done()` returns True at the end of the iteration
- **THEN** the loop SHALL set status to `"done"` and exit
- **AND** the orchestrator SHALL re-verify the change

#### Scenario: Agent fails to fix within max iterations
- **WHEN** `_check_test_done()` returns False for all iterations up to `max_iterations`
- **THEN** the loop SHALL exit with status `"stopped"`
- **AND** the change status SHALL be set to `"failed"`

### Requirement: Re-review after successful retry
When a retry loop completes successfully (tests pass), the change SHALL re-enter the verification pipeline. If re-review passes, the change proceeds to merge. If re-review finds new issues, another retry cycle MAY be triggered (subject to `max_verify_retries`).

#### Scenario: Re-review passes after retry
- **WHEN** the retry loop exits with `"done"` status
- **AND** re-review finds no CRITICAL issues
- **THEN** the change SHALL proceed to merge

#### Scenario: Re-review finds new issues
- **WHEN** the retry loop exits with `"done"` status
- **AND** re-review finds new CRITICAL issues
- **AND** `max_verify_retries` has not been exceeded
- **THEN** a new retry cycle SHALL be triggered

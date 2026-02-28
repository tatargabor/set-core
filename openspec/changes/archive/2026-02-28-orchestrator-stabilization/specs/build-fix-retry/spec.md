## ADDED Requirements

### Requirement: Build failure retry path
WHEN a change fails with `build_result: "fail"` in the verify gate, the orchestrator SHALL offer a lightweight retry path: resume the agent in the worktree with the build error output as `retry_context`, rather than waiting for a full replan decomposition.

#### Scenario: Build failure triggers agent retry
- **WHEN** a change status is `"failed"` AND `build_result` is `"fail"` AND `gate_retry_count` is less than `max_verify_retries`
- **THEN** the orchestrator SHALL set `retry_context` to the build error output, increment `gate_retry_count`, and call `resume_change()` to let the agent fix the type error

#### Scenario: Build retry succeeds
- **WHEN** the agent fixes the build error and the loop completes
- **THEN** the verify gate SHALL re-run from the build step and proceed normally on success

#### Scenario: Build retry exhausted
- **WHEN** `gate_retry_count` reaches `max_verify_retries` and build still fails
- **THEN** the change SHALL remain in `"failed"` status and be reported in orchestration summary

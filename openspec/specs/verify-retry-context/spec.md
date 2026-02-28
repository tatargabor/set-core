# verify-retry-context Specification

## Purpose
TBD - created by archiving change verify-gate-retry-improvements. Update Purpose after archive.
## Requirements
### Requirement: resume_change passes retry context to agent
When `resume_change()` is called after a verify gate failure, it SHALL read the `retry_context` field from orchestration state and include it in the task description passed to `wt-loop`.

#### Scenario: Test failure retry includes test output
- **WHEN** `resume_change()` is called for a change with `retry_context` set in state
- **THEN** the task description SHALL contain the retry context content (test command, test output, original scope)
- **AND** the generic "Continue $change_name" fallback SHALL NOT be used

#### Scenario: Resume without retry context uses fallback
- **WHEN** `resume_change()` is called for a change with no `retry_context` in state
- **THEN** the task description SHALL be the existing generic format: "Continue $change_name: $scope"

#### Scenario: Retry context cleared after use
- **WHEN** `resume_change()` reads and uses `retry_context`
- **THEN** the `retry_context` field SHALL be cleared from state to prevent stale context on future resumes

### Requirement: Merge conflict triggers agent-assisted rebase
When a merge conflict occurs and LLM resolution fails, the orchestrator SHALL resume the agent in the worktree to rebase the branch onto main, instead of blindly retrying the same merge.

#### Scenario: First merge conflict triggers agent rebase
- **WHEN** `merge_change()` fails due to merge conflict (wt-merge returns non-zero)
- **AND** `merge_retry_count` is 0 (first attempt)
- **THEN** the orchestrator SHALL store a `retry_context` describing the merge conflict and requesting the agent to merge main into the branch
- **AND** the orchestrator SHALL call `resume_change()` to restart the agent in the worktree
- **AND** the status SHALL be set to `"merge-rebase"`

#### Scenario: Agent completes rebase, merge retried
- **WHEN** `handle_change_done()` fires for a change with status `"merge-rebase"`
- **THEN** the orchestrator SHALL skip the verify gate (tests/review/verify) and proceed directly to merge
- **AND** if the merge succeeds, the change SHALL be marked `"merged"`

#### Scenario: Fallback to retry_merge_queue after agent rebase
- **WHEN** the agent-assisted rebase completes but the merge still fails
- **THEN** the change SHALL enter the existing `retry_merge_queue` flow with remaining retries
- **AND** the `merge_retry_count` SHALL be incremented

### Requirement: Memory recall enriches retry prompts
Before resuming an agent for any retry (test failure, review failure, merge conflict), the orchestrator SHALL recall relevant memories and include them in the retry prompt.

#### Scenario: Memory recalled before test failure retry
- **WHEN** a test failure triggers a retry via `resume_change()`
- **THEN** the orchestrator SHALL call `orch_recall` with the change scope as query and no tag filter
- **AND** if recall returns non-empty content, it SHALL be appended to the retry context as a `## Context from Memory` section
- **AND** the memory section SHALL be limited to 1000 characters

#### Scenario: Memory recalled before merge conflict rebase
- **WHEN** a merge conflict triggers agent-assisted rebase
- **THEN** the orchestrator SHALL call `orch_recall` with query including the change name and "merge conflict"
- **AND** recalled content (e.g., what other changes recently merged) SHALL be included in the rebase task prompt

#### Scenario: No memories available
- **WHEN** `orch_recall` returns empty
- **THEN** the `## Context from Memory` section SHALL be omitted from the retry prompt

### Requirement: Review failure retry includes review feedback
When a code review finds CRITICAL issues and triggers a retry, the retry context SHALL include the review output.

#### Scenario: Review critical retry context
- **WHEN** `handle_change_done()` triggers a retry due to CRITICAL review issues
- **THEN** the `retry_context` SHALL include the review output (truncated to first 500 chars)
- **AND** the retry context SHALL describe what review issues were found


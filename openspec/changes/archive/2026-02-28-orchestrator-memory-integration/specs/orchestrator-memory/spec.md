## ADDED Requirements

### Requirement: Helper functions for orchestrator memory access
The orchestrator SHALL provide `orch_remember` and `orch_recall` helper functions that encapsulate set-memory CLI access with consistent tagging, availability checks, and failure handling.

#### Scenario: orch_remember saves with orchestrator tags
- **WHEN** `orch_remember "merge conflict between X and Y" Learning "phase:merge,change:my-change"` is called
- **THEN** the content SHALL be saved via `set-memory remember` with type `Learning` and tags `source:orchestrator,phase:merge,change:my-change`
- **AND** the function SHALL return 0 regardless of set-memory success or failure

#### Scenario: orch_remember when set-memory is not installed
- **WHEN** `orch_remember` is called and `set-memory` is not on PATH
- **THEN** the function SHALL return 0 immediately without error

#### Scenario: orch_recall retrieves filtered memories
- **WHEN** `orch_recall "merge conflicts" 3 "source:orchestrator,phase:merge"` is called
- **THEN** the function SHALL return memory content as plain text, limited to 2000 characters
- **AND** the function SHALL use hybrid recall mode

#### Scenario: orch_recall when set-memory is not installed
- **WHEN** `orch_recall` is called and `set-memory` is not on PATH
- **THEN** the function SHALL return empty string and exit 0

### Requirement: Orchestrator saves merge outcomes as memories
The orchestrator SHALL save a memory after each merge attempt with the outcome (success, conflict, or already-merged).

#### Scenario: Successful merge saved
- **WHEN** `merge_change()` successfully merges a change
- **THEN** the orchestrator SHALL call `orch_remember` with type `Context`, tags `phase:merge,change:<name>`, and content describing the successful merge including change name and iteration count

#### Scenario: Merge conflict saved
- **WHEN** `merge_change()` encounters a merge conflict
- **THEN** the orchestrator SHALL call `orch_remember` with type `Decision`, tags `phase:merge,change:<name>`, and content describing the conflict including change name
- **AND** the content SHALL note that this change conflicted so future planning can sequence it differently

#### Scenario: Merge conflict after max retries saved
- **WHEN** `retry_merge_queue()` exhausts all retry attempts for a change
- **THEN** the orchestrator SHALL call `orch_remember` with type `Decision`, tags `phase:merge,change:<name>`, and content noting permanent merge failure

### Requirement: Orchestrator saves test outcomes as memories
The orchestrator SHALL save a memory after each test execution with the pass/fail outcome.

#### Scenario: Test pass saved
- **WHEN** `handle_change_done()` runs tests and they pass
- **THEN** the orchestrator SHALL call `orch_remember` with type `Context`, tags `phase:test,change:<name>`, and content noting test success

#### Scenario: Test failure saved
- **WHEN** `handle_change_done()` runs tests and they fail
- **THEN** the orchestrator SHALL call `orch_remember` with type `Learning`, tags `phase:test,change:<name>`, and content including the change name and truncated test output (first 500 chars)

### Requirement: Orchestrator saves review outcomes as memories
The orchestrator SHALL save a memory after each code review with the outcome.

#### Scenario: Review pass saved
- **WHEN** `review_change()` completes with no CRITICAL issues
- **THEN** the orchestrator SHALL call `orch_remember` with type `Context`, tags `phase:review,change:<name>`, and content noting review passed

#### Scenario: Review with critical issues saved
- **WHEN** `review_change()` finds CRITICAL issues
- **THEN** the orchestrator SHALL call `orch_remember` with type `Learning`, tags `phase:review,change:<name>`, and content including the change name and truncated review output (first 500 chars)

### Requirement: Orchestrator saves stall/failure events as memories
The orchestrator SHALL save a memory when a change stalls or fails permanently.

#### Scenario: Change stall saved
- **WHEN** `poll_change()` detects a stalled/stuck change and stall_count exceeds the max retries (give-up branch, stall_count > 3)
- **THEN** the orchestrator SHALL call `orch_remember` with type `Learning`, tags `phase:monitor,change:<name>`, and content noting the change stalled after max attempts
- **NOTE**: The memory save fires when the change is marked as "failed" (the give-up branch), not on the last retry attempt

#### Scenario: Change failure saved
- **WHEN** a change transitions to `failed` status
- **THEN** the orchestrator SHALL call `orch_remember` with type `Learning`, tags `phase:monitor,change:<name>`, and content noting the failure reason

### Requirement: Per-roadmap-item recall during planning
During `cmd_plan()`, the orchestrator SHALL recall memories specific to each roadmap item's scope text instead of using a single generic query.

#### Scenario: Brief mode per-item recall
- **WHEN** `cmd_plan()` operates in brief mode with multiple roadmap items
- **THEN** for each item, the orchestrator SHALL call `orch_recall` with the item's scope text as query and no tag filter (to capture both agent and orchestrator memories)
- **AND** the combined recalled context SHALL be injected into the planning prompt as `## Project Memory`

#### Scenario: Spec mode recall
- **WHEN** `cmd_plan()` operates in spec mode
- **THEN** the orchestrator SHALL recall using the spec summary or phase hint as query
- **AND** additionally recall `source:orchestrator` tagged memories for operational context

#### Scenario: Recall produces no results
- **WHEN** recall returns empty for all items
- **THEN** the `## Project Memory` section SHALL be omitted from the prompt (not included as empty)

### Requirement: Replan recalls orchestrator operational history
During `auto_replan_cycle()`, the orchestrator SHALL recall memories from the current orchestration cycle to inform the replanning prompt.

#### Scenario: Replan with merge conflict history
- **WHEN** `auto_replan_cycle()` runs and past merge conflicts exist in memory
- **THEN** the recalled memories SHALL be injected into the planning prompt as `## Orchestration History`
- **AND** the section SHALL appear after the completed items context

#### Scenario: Replan recall query
- **WHEN** `auto_replan_cycle()` performs recall
- **THEN** the query SHALL be `"orchestration merge conflict test failure review"` with tags `source:orchestrator` and limit 5
- **AND** results SHALL be injected as `## Orchestration History` section via `_REPLAN_MEMORY` env var

#### Scenario: Replan with no orchestrator memories
- **WHEN** `auto_replan_cycle()` recalls and no orchestrator memories exist
- **THEN** the `## Orchestration History` section SHALL be omitted

### Requirement: Dispatch enriches proposal with recalled memories
When `dispatch_change()` creates a proposal.md in a worktree, it SHALL recall memories relevant to the change scope and append them to the proposal.

#### Scenario: Dispatch with relevant memories
- **WHEN** `dispatch_change()` creates proposal.md for a change
- **AND** `orch_recall` returns non-empty content for the change scope
- **THEN** the proposal.md SHALL include a `## Context from Memory` section after the `## Impact` section
- **AND** the section content SHALL be limited to 1000 characters

#### Scenario: Dispatch with no relevant memories
- **WHEN** `dispatch_change()` creates proposal.md for a change
- **AND** `orch_recall` returns empty for the change scope
- **THEN** proposal.md SHALL NOT include the `## Context from Memory` section

#### Scenario: Dispatch recall uses scope text
- **WHEN** `dispatch_change()` performs recall
- **THEN** the query SHALL use the change's scope text (not the kebab-case name)
- **AND** the recall SHALL NOT filter by `source:orchestrator` tags (to capture both agent and orchestrator memories)

### Requirement: Memory audit periodic health check
The orchestrator SHALL run `orch_memory_audit()` periodically during the monitor loop (approximately every 10 poll cycles). The audit SHALL check set-memory health, count orchestrator memories, and spot-check the latest memory content.

#### Scenario: Memory system healthy
- **WHEN** orch_memory_audit runs and set-memory health returns OK
- **THEN** the audit SHALL log memory count and pass silently

#### Scenario: Memory system unhealthy
- **WHEN** set-memory health fails or memory count is 0
- **THEN** the audit SHALL log a warning but NOT block orchestration

### Requirement: Quality gate steps are timed
Each quality gate step in `handle_change_done()` SHALL measure elapsed wall-clock time in milliseconds and store the result in the change's state.

#### Scenario: Test execution timed
- **WHEN** `run_tests_in_worktree()` is called within `handle_change_done()`
- **THEN** the elapsed time SHALL be measured via epoch milliseconds before/after
- **AND** stored in the change state as `gate_test_ms`

#### Scenario: LLM review timed
- **WHEN** `review_change()` is called within `handle_change_done()`
- **THEN** the elapsed time SHALL be measured
- **AND** stored in the change state as `gate_review_ms`

#### Scenario: Verify step timed
- **WHEN** the `/opsx:verify` claude call runs within `handle_change_done()`
- **THEN** the elapsed time SHALL be measured
- **AND** stored in the change state as `gate_verify_ms`

### Requirement: Retry token cost is tracked
When a change fails verification and is retried via `resume_change()`, the orchestrator SHALL track the additional token cost of retry iterations.

#### Scenario: Retry token diff captured
- **WHEN** `handle_change_done()` triggers a retry (test fail or review critical)
- **THEN** the current `total_tokens` from loop-state.json SHALL be recorded as `retry_tokens_start`
- **AND** when `handle_change_done()` is called again after the retry loop completes, the diff `total_tokens - retry_tokens_start` SHALL be stored as `gate_retry_tokens`

#### Scenario: Multiple retries accumulate
- **WHEN** a change goes through multiple verify-retry cycles
- **THEN** `gate_retry_tokens` SHALL accumulate (add each cycle's diff)

### Requirement: Per-change gate cost summary in state
The orchestrator state JSON SHALL include a `gate_costs` object per change summarizing all quality gate costs.

#### Scenario: Gate costs stored after successful verification
- **WHEN** `handle_change_done()` completes all steps and marks the change as done
- **THEN** the change state SHALL include:
  - `gate_test_ms`: total test execution time (0 if skipped)
  - `gate_review_ms`: total review time (0 if skipped)
  - `gate_verify_ms`: total verify time
  - `gate_retry_tokens`: total tokens consumed by retry loops (0 if no retries)
  - `gate_retry_count`: number of retry cycles
  - `gate_total_ms`: sum of test + review + verify times

### Requirement: Aggregate gate cost log
The orchestrator SHALL log aggregate quality gate costs at orchestration completion and in periodic status reports.

#### Scenario: Completion summary includes gate costs
- **WHEN** orchestration reaches completion (all changes done or time limit)
- **THEN** the log SHALL include a summary line with: total gate time across all changes, total retry tokens, number of changes that needed retries, gate time as percentage of active time

#### Scenario: cmd_status shows gate costs
- **WHEN** `cmd_status` displays the change table
- **THEN** each change row SHALL include gate time (e.g., "23.7s") and retry info (e.g., "1 retry, +45k tokens")
- **AND** a summary row SHALL show aggregate gate costs

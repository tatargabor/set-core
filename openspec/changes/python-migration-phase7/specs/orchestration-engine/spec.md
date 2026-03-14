## ADDED Requirements

### Requirement: Monitor loop entry point
The system SHALL provide `monitor_loop(directives_json, state_file)` that runs the main orchestration monitoring loop, polling at a configurable interval until completion, stop, or time limit.

#### Scenario: Normal poll cycle
- **WHEN** the monitor loop runs a poll iteration
- **THEN** the system SHALL poll all active changes (running + verifying), check suspended changes for completed loop-state, process verify-failed recovery, cascade failed deps, dispatch ready changes, retry merge queue, resume stalled changes, retry failed builds, check completion, and update the HTML report

#### Scenario: External stop
- **WHEN** the orchestrator state status is "stopped" or "done"
- **THEN** the system SHALL generate a final report, run coverage check, and exit the loop

#### Scenario: Paused or checkpoint
- **WHEN** the orchestrator state status is "paused" or "checkpoint"
- **THEN** the system SHALL skip the poll iteration and continue to next cycle

### Requirement: Directive parsing
The system SHALL parse all ~40 orchestration directives from JSON input into a structured `Directives` object, with defaults matching the bash global constants.

#### Scenario: All directives present
- **WHEN** the directives JSON includes all fields
- **THEN** the system SHALL parse them into typed fields (int, bool, str) with no jq dependency

#### Scenario: Missing optional directives
- **WHEN** optional directives are omitted
- **THEN** the system SHALL use default values matching the bash constants (e.g., test_timeout=300, max_verify_retries=1, review_model="opus")

### Requirement: Token budget enforcement
The system SHALL enforce a soft token budget that pauses new dispatches while allowing running loops to finish, and a hard token limit that triggers a checkpoint for human approval.

#### Scenario: Soft budget exceeded
- **WHEN** total tokens across all changes exceed token_budget
- **THEN** the system SHALL stop dispatching new changes but continue polling running ones and retrying merge queue

#### Scenario: Soft budget recovered
- **WHEN** total tokens drop below token_budget (after loops finish)
- **THEN** the system SHALL resume dispatching

#### Scenario: Hard limit reached
- **WHEN** cumulative tokens (including previous replan cycles) exceed token_hard_limit
- **THEN** the system SHALL trigger a checkpoint for human approval and raise the limit for next checkpoint

### Requirement: Time limit enforcement
The system SHALL enforce a configurable time limit based on active time (not wall clock), where active time only counts poll intervals when loops are making progress.

#### Scenario: Time limit reached
- **WHEN** active_seconds exceeds the configured time limit
- **THEN** the system SHALL set status to "time_limit", send notification, send summary email, generate report, and exit

#### Scenario: Time limit disabled
- **WHEN** time_limit is "none" or "0"
- **THEN** the system SHALL run indefinitely until completion or external stop

### Requirement: Self-watchdog
The system SHALL detect all-idle stalls where no progress has been made within a configurable timeout.

#### Scenario: First idle timeout
- **WHEN** no progress for monitor_idle_timeout seconds (first occurrence)
- **THEN** the system SHALL attempt recovery by retrying merge queue and adding orphaned "done" changes to the queue

#### Scenario: Persistent idle
- **WHEN** no progress persists through multiple idle timeouts
- **THEN** the system SHALL emit MONITOR_STALL event, send critical notification, and reset the timer

### Requirement: Verify-failed recovery
The system SHALL automatically recover verify-failed changes by resuming them with retry context, up to max_verify_retries.

#### Scenario: Retry available
- **WHEN** a change has status "verify-failed" and verify_retry_count < max_verify_retries
- **THEN** the system SHALL increment retry count, rebuild retry_context from stored build_output if missing, and resume the change

#### Scenario: Retries exhausted
- **WHEN** a change has status "verify-failed" and verify_retry_count >= max_verify_retries
- **THEN** the system SHALL mark the change as "failed"

### Requirement: Completion detection
The system SHALL detect when all changes have reached terminal status (merged, done, skipped, failed, merge-blocked) and handle completion including phase-end E2E, post-phase audit, auto-replan, or checkpoint.

#### Scenario: All changes complete with auto-replan
- **WHEN** all changes are terminal and auto_replan is true
- **THEN** the system SHALL run auto_replan_cycle, continue monitoring on success, mark "done" if no new work, or retry on failure up to MAX_REPLAN_RETRIES

#### Scenario: All changes complete without auto-replan
- **WHEN** all changes are terminal and auto_replan is false
- **THEN** the system SHALL trigger completion checkpoint, set status "done", cleanup worktrees, tag orch/complete, and send summary email

#### Scenario: Partial completion
- **WHEN** no active changes remain but some are failed or merge-blocked
- **THEN** the system SHALL transition to done with partial completion notification

### Requirement: Phase milestone integration
The system SHALL check for phase completion when milestones are enabled and advance to the next phase.

#### Scenario: Phase complete
- **WHEN** milestones are enabled and all changes in the current phase are terminal
- **THEN** the system SHALL run milestone checkpoint and advance to the next phase

### Requirement: Suspended change recovery
The system SHALL check paused, waiting:budget, budget_exceeded, and done changes for completed loop-state as a safety net against race conditions.

#### Scenario: Suspended change with done loop-state
- **WHEN** a suspended change has loop-state.json with status "done"
- **THEN** the system SHALL temporarily set the change to "running" and process it via poll_change

#### Scenario: Orphaned done change
- **WHEN** a change has status "done" but is not in the merge queue
- **THEN** the system SHALL add it to the merge queue

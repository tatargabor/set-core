## ADDED Requirements

### Requirement: Shared resource awareness in planner prompt
The decomposition prompt SHALL include a shared resource rule instructing the LLM to serialize changes that would modify the same shared files.

#### Scenario: Shared resource rule in spec-mode prompt
- **WHEN** the spec-mode decomposition prompt is constructed
- **THEN** it SHALL include a SHARED RESOURCE RULE section after existing dependency rules
- **AND** the rule SHALL instruct the LLM to chain changes via `depends_on` when they would modify the same shared file (conventions docs, shared types, config files, common UI components)

#### Scenario: Shared resource rule in brief-mode prompt
- **WHEN** the brief-mode decomposition prompt is constructed
- **THEN** it SHALL include the same SHARED RESOURCE RULE section

### Requirement: Replan cycle boundary markers
The orchestrator SHALL emit explicit boundary markers when a new replan cycle starts.

#### Scenario: Log separator on replan
- **WHEN** `auto_replan_cycle()` begins a new cycle
- **THEN** the orchestrator SHALL emit a `log_info` line with format `========== REPLAN CYCLE <N> ==========`

#### Scenario: Cycle timestamp in state
- **WHEN** a new replan cycle initializes
- **THEN** the orchestrator SHALL set `cycle_started_at` to the current ISO-8601 timestamp in `orchestration-state.json`

## MODIFIED Requirements

### Requirement: Monitor loop polling
The orchestrator monitor loop SHALL poll active changes every 15 seconds.

#### Scenario: Poll interval
- **WHEN** the monitor loop is running
- **THEN** it SHALL sleep for `POLL_INTERVAL` (15) seconds between poll cycles

#### Scenario: Active time tracking
- **WHEN** polling and at least one Ralph loop is making progress (loop-state.json mtime < 5 minutes)
- **THEN** the orchestrator SHALL increment `active_seconds` by `POLL_INTERVAL`
- **AND** NOT count time during token budget wait or when all loops are stalled

#### Scenario: Stale loop-state with live PID
- **WHEN** a change's loop-state.json has not been updated in 300+ seconds
- **AND** the terminal PID is still alive
- **THEN** the orchestrator SHALL log at `log_debug` level (not `log_info`)
- **AND** the message SHALL indicate "long iteration, skipping"

### Requirement: Auto-replan system
The orchestrator SHALL support automatic replanning when all changes complete.

#### Scenario: Auto-replan on completion
- **WHEN** all changes reach terminal status (done/merged/merge-blocked/failed)
- **AND** `auto_replan` directive is true
- **THEN** the orchestrator SHALL re-run `cmd_plan` with completed roadmap items as context
- **AND** if new changes are found (rc=0), dispatch them and continue monitoring
- **AND** if no new work (rc=1), set status to `done` and exit
- **AND** if plan fails (rc=2), retry up to `MAX_REPLAN_RETRIES` (3) before giving up

#### Scenario: Replan preserves cumulative state
- **WHEN** a replan cycle reinitializes state
- **THEN** the orchestrator SHALL preserve `active_seconds`, `started_epoch`, `time_limit_secs`, `prev_total_tokens`, and `cycle_started_at`

#### Scenario: Failed change deduplication in replan
- **WHEN** a replan produces only previously-failed change names
- **THEN** the orchestrator SHALL return rc=1 (no new work) instead of dispatching the same failures

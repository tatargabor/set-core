## MODIFIED Requirements

### Requirement: Header status display
The TUI SHALL display orchestrator status in a header bar.

#### Scenario: Running state header
- **WHEN** the orchestrator status is `running`
- **THEN** the header SHALL show: status indicator, plan version (with replan cycle if >0), progress ratio (merged+done/total), cumulative tokens, active time / time limit with remaining

#### Scenario: Token counter during replan transition
- **WHEN** a replan cycle has just started
- **AND** current cycle token sum is 0
- **AND** `prev_total_tokens` is greater than 0
- **THEN** the header SHALL display `prev_total_tokens` as the total token count
- **AND** SHALL NOT display zero or dash

#### Scenario: Checkpoint state header
- **WHEN** the orchestrator status is `checkpoint`
- **THEN** the header SHALL display a highlighted/blinking checkpoint indicator

#### Scenario: Time limit exceeded header
- **WHEN** the orchestrator status is `time_limit`
- **THEN** the header SHALL display a yellow time limit indicator

### Requirement: Live log tail
The TUI SHALL display the orchestration log with auto-scroll.

#### Scenario: Log display
- **WHEN** `.claude/orchestration.log` exists
- **THEN** the TUI SHALL display the last ~200 lines with color by level: INFO=default, WARN=yellow, ERROR=red
- **AND** update within 3-5 seconds

#### Scenario: Replan cycle boundary in log
- **WHEN** a log line matches the pattern `========== REPLAN CYCLE`
- **THEN** the TUI SHALL render it with highlighted/bold styling to visually separate cycles

#### Scenario: Missing log
- **WHEN** the log file does not exist
- **THEN** the TUI SHALL display "No log file yet" dimmed

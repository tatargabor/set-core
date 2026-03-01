## ADDED Requirements

### Requirement: Per-iteration log files
The Ralph loop SHALL write each Claude invocation's output to a separate log file for post-mortem analysis.

#### Scenario: Log directory creation on loop start
- **WHEN** `cmd_run()` starts
- **THEN** the directory `.claude/logs/` SHALL be created if it does not exist

#### Scenario: Per-iteration log file naming
- **WHEN** iteration N starts
- **THEN** Claude output SHALL be written to `.claude/logs/ralph-iter-NNN.log` where NNN is zero-padded to 3 digits
- **AND** the log file path SHALL be stored in the iteration record in `loop-state.json`

#### Scenario: Log captures full Claude output
- **WHEN** Claude runs during an iteration
- **THEN** the log file SHALL contain all stdout and stderr from the Claude process
- **AND** the output SHALL also appear on the terminal in real-time (tee behavior)

#### Scenario: Log files persist across iterations
- **WHEN** a new iteration starts
- **THEN** previous iteration log files SHALL NOT be deleted
- **AND** all log files from the current loop run SHALL remain in `.claude/logs/`

### Requirement: Post-iteration log summary
The Ralph loop SHALL display a brief summary of key events extracted from the iteration log after each Claude invocation completes.

#### Scenario: Summary displays after iteration
- **WHEN** a Claude invocation completes
- **THEN** the Ralph loop SHALL scan the iteration log file
- **AND** display a summary including: number of files read/written, skills invoked, errors encountered

#### Scenario: Summary handles empty or missing log
- **WHEN** the iteration log file is empty or missing
- **THEN** the summary SHALL display "No log output captured"
- **AND** the loop SHALL continue normally

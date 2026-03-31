## MODIFIED Requirements

### Requirement: Per-iteration log files
The Ralph loop SHALL write each Claude invocation's output to a separate log file for post-mortem analysis. The iteration record SHALL additionally include `context_breakdown` fields for context composition analysis.

#### Scenario: Log directory creation on loop start
- **WHEN** `cmd_run()` starts
- **THEN** the directory `.set/logs/` SHALL be created if it does not exist

#### Scenario: Per-iteration log file naming
- **WHEN** iteration N starts
- **THEN** Claude output SHALL be written to `.set/logs/ralph-iter-NNN.log` where NNN is zero-padded to 3 digits
- **AND** the log file path SHALL be stored in the iteration record in `loop-state.json`

#### Scenario: Log captures full Claude output
- **WHEN** Claude runs during an iteration
- **THEN** the log file SHALL contain all stdout and stderr from the Claude process
- **AND** the output SHALL also appear on the terminal in real-time (tee behavior)

#### Scenario: Log files persist across iterations
- **WHEN** a new iteration starts
- **THEN** previous iteration log files SHALL NOT be deleted
- **AND** all log files from the current loop run SHALL remain in `.set/logs/`

#### Scenario: Iteration record includes context breakdown
- **WHEN** an iteration completes and tokens are recorded
- **THEN** the iteration record in `loop-state.json` SHALL include a `context_breakdown` object with keys: `base_context`, `memory_injection`, `prompt_overhead`, `tool_output`
- **AND** each value SHALL be an integer token count (0 if not measurable)

## ADDED Requirements

### Requirement: Real-time terminal output via PTY wrapper
The Ralph loop SHALL display Claude's output in real-time during execution using a PTY wrapper.

#### Scenario: PTY wrapper for line-buffered output
- **WHEN** Claude is invoked during an iteration
- **THEN** the invocation SHALL use `script -f -q -c "claude ..."` (Linux) or equivalent PTY wrapper
- **AND** output SHALL appear on the terminal as it is generated (line-buffered, not block-buffered)
- **AND** output SHALL simultaneously be written to the per-iteration log file

#### Scenario: Fallback when script command unavailable
- **WHEN** the `script` command is not available
- **THEN** the Ralph loop SHALL fall back to direct pipe invocation (`echo "$prompt" | claude`)
- **AND** log a warning: "PTY wrapper unavailable, output may be buffered"

### Requirement: Verbose mode for tool use visibility
The Ralph loop SHALL enable verbose output so tool use events are visible during execution.

#### Scenario: Verbose flag always enabled
- **WHEN** Claude is invoked during a Ralph loop iteration
- **THEN** the `--verbose` flag SHALL be passed to the Claude CLI
- **AND** tool use events (file reads, edits, skill invocations) SHALL be visible in the terminal

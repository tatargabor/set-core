## MODIFIED Requirements

### Requirement: Real-time terminal output during iterations
The Ralph loop SHALL display Claude output in real-time during each iteration, not buffered until completion.

#### Scenario: Line-buffered output with stdbuf available
- **WHEN** `stdbuf` is available on the system
- **THEN** the Claude invocation pipe SHALL use `stdbuf -oL` for both `claude` and `tee` commands
- **AND** terminal output SHALL appear line-by-line as Claude generates it

#### Scenario: Fallback without stdbuf
- **WHEN** `stdbuf` is not available on the system
- **THEN** the Claude invocation pipe SHALL fall back to the existing unbuffered pipe
- **AND** a one-time warning SHALL be logged: "stdbuf not found — output may be buffered"

## ADDED Requirements

### Requirement: Output-level idle iteration detection
When the loop produces identical output across consecutive iterations, it SHALL be detected and stopped.

#### Scenario: Identical output triggers idle stop
- **WHEN** a loop iteration completes
- **AND** the MD5 hash of the last 200 lines of iteration output matches the previous iteration's hash
- **AND** this match has occurred `max_idle_iterations` consecutive times (default: 3)
- **THEN** the loop SHALL stop with status `idle`
- **AND** `loop-state.json` SHALL record `idle_count` and `last_output_hash`

#### Scenario: Different output resets idle counter
- **WHEN** a loop iteration completes
- **AND** the output hash differs from the previous iteration
- **THEN** `idle_count` SHALL be reset to 0
- **AND** `last_output_hash` SHALL be updated to the new hash

#### Scenario: Idle detection is independent of stall detection
- **WHEN** the loop has existing stall detection (commit-based, `stall_threshold`)
- **THEN** idle detection (output-based) SHALL operate independently
- **AND** either mechanism can stop the loop

#### Scenario: Configurable threshold
- **WHEN** `wt-loop` is started with `--max-idle N`
- **THEN** `max_idle_iterations` SHALL be set to N
- **AND** stored in `loop-state.json`
- **AND** default SHALL be 3 if not specified

#### Scenario: Hash computation
- **WHEN** computing the output hash
- **THEN** the last 200 lines of the iteration log file SHALL be used
- **AND** the hash SHALL be MD5 (`md5sum | cut -d' ' -f1`)
- **AND** if the log file has fewer than 200 lines, the entire file SHALL be used

#### Scenario: First iteration has no previous hash
- **WHEN** the first iteration completes
- **THEN** `last_output_hash` SHALL be set
- **AND** `idle_count` SHALL remain 0 (nothing to compare against)

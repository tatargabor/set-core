## MODIFIED Requirements

### Requirement: Graceful degradation
If shodh-memory is not installed, both `audit` and `dedup` commands SHALL exit silently with code 0 and appropriate empty output (empty report or `{"deleted_count": 0}`). The session-end memory hook SHALL also respect the no-op marker to avoid saving redundant memories during unproductive loop iterations.

#### Scenario: Shodh-memory not installed
- **WHEN** `wt-memory audit` or `wt-memory dedup` is run without shodh-memory installed
- **THEN** the command exits 0 with no error output

#### Scenario: Session-end hook skips save on no-op marker
- **WHEN** the session-end memory extraction hook (`wt-hook-stop`) runs
- **AND** the file `.claude/loop-iteration-noop` exists in the worktree
- **AND** the marker file timestamp is less than 1 hour old
- **THEN** the hook SHALL skip memory extraction
- **AND** the hook SHALL log: "Skipping memory save — no-op loop iteration"
- **AND** the marker file SHALL be removed after being read

#### Scenario: Session-end hook runs normally without marker
- **WHEN** the session-end memory extraction hook runs
- **AND** no `.claude/loop-iteration-noop` file exists
- **THEN** memory extraction proceeds as normal

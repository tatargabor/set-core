# loop-idle-detection Specification

## Purpose
Detect and handle Ralph loop iterations that produce no useful work — FF retry limits, no-op markers, and auto-stop for unproductive loops.

## Requirements

### Requirement: FF retry limit prevents infinite artifact creation loops
The Ralph loop SHALL track consecutive failed `ff:` attempts per change and stop retrying after a configurable maximum.

#### Scenario: FF creates tasks.md successfully
- **WHEN** the Ralph loop runs an `ff:` action for a change
- **AND** after the iteration, `tasks.md` exists in the change directory
- **THEN** the ff attempt counter SHALL be reset to 0
- **AND** the next iteration SHALL proceed normally

#### Scenario: FF fails to create tasks.md
- **WHEN** the Ralph loop runs an `ff:` action for a change
- **AND** after the iteration, `tasks.md` does NOT exist in the change directory
- **THEN** the ff attempt counter SHALL be incremented
- **AND** a warning SHALL be logged: "FF attempt {n}/{max} failed — tasks.md not created"

#### Scenario: FF retry limit exceeded
- **WHEN** the ff attempt counter reaches the maximum (default: 2)
- **THEN** the loop SHALL stop with status `"stalled"`
- **AND** the status message SHALL include: "FF failed to create tasks.md after {max} attempts"
- **AND** the iteration record SHALL include `"ff_exhausted": true`

#### Scenario: FF retry limit is configurable
- **WHEN** the Ralph loop state includes `ff_max_retries` (set by orchestrator)
- **THEN** that value SHALL be used instead of the default 2

### Requirement: No-op iteration marker for downstream hooks
The Ralph loop SHALL create a marker file when an iteration produces no meaningful work, so session-end hooks can skip redundant memory saves.

#### Scenario: No-op iteration detected
- **WHEN** an iteration completes with no commits
- **AND** no new or modified files exist (clean working tree)
- **THEN** the Ralph loop SHALL create `.claude/loop-iteration-noop` containing the current ISO timestamp
- **AND** the iteration record SHALL include `"no_op": true`

#### Scenario: Productive iteration cleans marker
- **WHEN** an iteration produces commits or new files
- **THEN** the `.claude/loop-iteration-noop` marker SHALL be removed if it exists

#### Scenario: Session-end hook respects no-op marker
- **WHEN** the session-end hook runs
- **AND** `.claude/loop-iteration-noop` exists
- **AND** the marker timestamp is less than 1 hour old
- **THEN** the hook SHALL skip memory extraction for this session

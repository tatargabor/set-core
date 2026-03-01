## ADDED Requirements

### Requirement: Session ID tracking
The Ralph loop SHALL assign and track a Claude session ID for resume-based continuation across iterations.

#### Scenario: First iteration assigns session ID
- **WHEN** the first iteration of a loop starts
- **AND** no session ID exists in `loop-state.json`
- **THEN** the Ralph loop SHALL generate a UUID
- **AND** pass `--session-id <uuid>` to the Claude CLI
- **AND** store the UUID in `loop-state.json` as `session_id`

#### Scenario: Session ID persists in state
- **WHEN** `loop-state.json` is written or updated
- **THEN** the `session_id` field SHALL contain the current session UUID
- **AND** the field SHALL persist across iterations

### Requirement: Session resume on subsequent iterations
The Ralph loop SHALL resume the existing Claude session instead of starting a new one on subsequent iterations.

#### Scenario: Resume with existing session ID
- **WHEN** iteration N > 1 starts
- **AND** `session_id` exists in `loop-state.json`
- **THEN** the Claude CLI SHALL be invoked with `--resume <session_id>`
- **AND** the prompt SHALL be a short continuation message instead of the full task prompt

#### Scenario: Continuation prompt is minimal
- **WHEN** a resumed iteration starts
- **THEN** the prompt SHALL be: "Continue where you left off. Check the task status and complete remaining work."
- **AND** the prompt SHALL NOT repeat CLAUDE.md reading instructions, full task description, or openspec context

#### Scenario: Resume failure fallback
- **WHEN** `--resume <session_id>` fails (non-zero exit code within 5 seconds)
- **THEN** the Ralph loop SHALL generate a new UUID
- **AND** start a fresh session with the full task prompt
- **AND** update `session_id` in `loop-state.json` with the new UUID
- **AND** log a warning: "Session resume failed, starting fresh session"

#### Scenario: Resume failure count tracking
- **WHEN** a resume failure occurs
- **THEN** the Ralph loop SHALL increment `resume_failures` in `loop-state.json`
- **AND** if `resume_failures >= 3`, all subsequent iterations SHALL use fresh sessions (no resume attempts)
- **AND** log: "Too many resume failures, switching to fresh session mode"

# Investigation Runner

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Spawn claude CLI as investigation agent in set-core directory
- Pluggable investigation templates (default + profile-provided)
- Structured diagnosis output parsing (DIAGNOSIS_START/END markers)
- Investigation timeout enforcement
- Resumable sessions for per-issue chat
- Investigation report persistence (.set/issues/investigations/)

### Out of scope
- Running investigation in project directory (always set-core)
- Multiple investigation agents per issue
- Streaming investigation output to UI in real-time

## Requirements

### Requirement: Investigation agent spawning
The runner SHALL spawn `claude -p` as a subprocess in the set-core directory with the investigation template as prompt. Output SHALL be captured to a file at `.set/issues/investigations/{issue_id}.md`.

#### Scenario: Spawn investigation
- **WHEN** the state machine triggers investigation for ISS-001
- **THEN** a claude CLI process is spawned in set-core dir with the rendered template, PID is tracked

#### Scenario: Investigation in set-core directory
- **WHEN** the investigation agent runs
- **THEN** its working directory is the set-core repo root, allowing it to read framework source code

### Requirement: Pluggable templates
The runner SHALL resolve investigation templates in order: (1) profile-provided template, (2) config-specified template name, (3) default template. Templates SHALL receive issue context variables for rendering.

#### Scenario: Profile template used
- **WHEN** the active profile provides an investigation_template method that returns a template
- **THEN** that template is used instead of the default

#### Scenario: Default template fallback
- **WHEN** no profile template is available and config says template="default"
- **THEN** the default template from templates/default.md is used

### Requirement: Diagnosis output parsing
The runner SHALL parse investigation output for a JSON block between DIAGNOSIS_START and DIAGNOSIS_END markers. If markers are absent, it SHALL try to find a JSON block in a markdown code fence at the end. If parsing fails, it SHALL create a fallback Diagnosis with confidence=0.0.

#### Scenario: Successful parse
- **WHEN** investigation output contains DIAGNOSIS_START {...} DIAGNOSIS_END
- **THEN** the JSON is parsed into a Diagnosis dataclass with all fields populated

#### Scenario: Parse failure fallback
- **WHEN** investigation output has no parseable diagnosis JSON
- **THEN** a Diagnosis with confidence=0.0 and root_cause="not parseable" is created, raw_output is preserved

### Requirement: Investigation timeout
The runner SHALL enforce a configurable timeout (default 300s). When exceeded, the agent process SHALL be killed.

#### Scenario: Timeout reached
- **WHEN** investigation has been running for longer than timeout_seconds
- **THEN** the agent process is killed and an "investigation_timeout" audit event is logged

### Requirement: Session resumability
The runner SHALL track the claude session ID for each investigation. This allows the per-issue chat (in the console) to resume the same session for follow-up questions.

#### Scenario: Chat resumes investigation session
- **WHEN** a user sends a message to ISS-001's console and investigation_session is set
- **THEN** the chat uses `claude -p --resume {session_id}` to continue the investigation context

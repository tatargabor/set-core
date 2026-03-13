## MODIFIED Requirements

### Requirement: Agent subprocess spawning
The chat session SHALL pass `--append-system-prompt` with dynamically built supervisor context on every claude subprocess invocation, in addition to existing flags (--resume, --output-format, --verbose, --permission-mode).

#### Scenario: System prompt passed on fresh session
- **WHEN** the first message is sent (no session_id yet)
- **THEN** claude is invoked with `--append-system-prompt "<context>"` alongside `--model` and `--permission-mode`

#### Scenario: System prompt passed on resumed session
- **WHEN** a follow-up message is sent (session_id exists)
- **THEN** claude is invoked with `--append-system-prompt "<context>"` alongside `--resume`

#### Scenario: Context refreshed between messages
- **WHEN** a change completes between the user's first and second message
- **THEN** the second invocation's system prompt reflects the updated state (change shown as done)

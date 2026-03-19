## ADDED Requirements

### Requirement: Send message via MCP

The system SHALL expose a `send_message()` MCP tool that allows agents to send directed messages to other agents or members.

#### Scenario: Send message to remote agent

- **WHEN** agent calls `send_message(recipient="tg@linux/gep2-linux", message="PONG received")`
- **THEN** the message is encrypted using the recipient's public key
- **AND** appended to the sender's outbox file
- **AND** committed and pushed to set-control
- **AND** returns `{"status": "sent", "id": "<uuid>", "ts": "<timestamp>"}`

#### Scenario: Send message without crypto

- **GIVEN** PyNaCl is not installed or no chat key exists
- **WHEN** agent calls `send_message()`
- **THEN** returns error message explaining how to set up chat keys

#### Scenario: Recipient not found

- **WHEN** agent calls `send_message(recipient="unknown@host", message="hello")`
- **THEN** returns error with list of available recipients

### Requirement: Read inbox via MCP

The system SHALL expose a `get_inbox()` MCP tool that returns directed messages for the current agent.

#### Scenario: Get all inbox messages

- **WHEN** agent calls `get_inbox()`
- **THEN** returns messages addressed to the current member
- **AND** messages are sorted by timestamp
- **AND** output format: `[timestamp] sender: message_text`

#### Scenario: Get inbox since timestamp

- **WHEN** agent calls `get_inbox(since="2026-02-08T08:00:00Z")`
- **THEN** returns only messages newer than the specified timestamp

#### Scenario: No messages

- **WHEN** agent calls `get_inbox()` and no messages exist
- **THEN** returns "No messages"

## MODIFIED Requirements

### Requirement: Query team status via MCP

The system SHALL expose a `get_team_status()` MCP tool that returns team member activity including broadcast messages.

#### Scenario: Team members active

- **WHEN** agent calls `get_team_status()`
- **THEN** returns list of team members
- **AND** each entry shows: name, agent_status (idle/working), change_id
- **AND** each entry shows broadcast message if present

#### Scenario: Team status unavailable

- **WHEN** GUI is not running or team sync disabled
- **THEN** returns "Team status not available"

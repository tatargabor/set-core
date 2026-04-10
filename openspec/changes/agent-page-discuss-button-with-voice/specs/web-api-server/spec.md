## MODIFIED Requirements

### Requirement: Chat WebSocket endpoint
The server SHALL expose `WS /ws/{project}/chat` that manages an interactive agent subprocess. Messages from the browser SHALL be written to the subprocess stdin. Subprocess stdout SHALL be parsed and forwarded to the browser as JSON events.

**The server MUST NOT spawn the agent subprocess automatically on WebSocket connect or on `new_session`.** A subprocess SHALL only be spawned in response to an explicit client message: either a user `{type: "message", content: ...}` or a new `{type: "start"}` message (defined below). On connect, the server SHALL replay history and current status only.

#### Scenario: Client connects with empty history
- **WHEN** a WebSocket client connects to `/ws/{project}/chat` and the session has no prior messages
- **THEN** the server sends `{"type": "history_replay", "messages": [], "status": "idle"}`
- **AND** the server does NOT spawn a claude subprocess
- **AND** no greeting is generated until the client sends a `start` or `message`

#### Scenario: Client connects with existing history
- **WHEN** a WebSocket client connects and the session already has messages
- **THEN** the server sends `{"type": "history_replay", "messages": [...], "status": "idle"}`
- **AND** the server does NOT spawn a claude subprocess

#### Scenario: Client sends start
- **WHEN** the client sends `{"type": "start"}` and `session.status == "idle"`
- **THEN** the server spawns a claude subprocess with an English greeting prompt ("Say hi and give a short orchestration status summary.")
- **AND** the agent response is streamed back via normal `assistant_text` / `tool_use` / `assistant_done` events

#### Scenario: Client sends start while already running
- **WHEN** the client sends `{"type": "start"}` and `session.status == "running"`
- **THEN** the server sends `{"type": "error", "message": "Already processing a message, please wait"}` and does not spawn another subprocess

#### Scenario: Client sends message
- **WHEN** a WebSocket client sends `{"type": "message", "content": "list worktrees"}`
- **THEN** the server spawns a claude subprocess, writes the message to stdin, and streams response events back to the client

#### Scenario: Client sends stop
- **WHEN** the client sends `{"type": "stop"}`
- **THEN** the server sends SIGTERM to the claude subprocess, waits for exit, and sends `{"type": "status", "status": "idle"}` to the client

#### Scenario: Client sends new_session
- **WHEN** the client sends `{"type": "new_session"}`
- **THEN** the server stops any running subprocess, clears `session.messages` and `session.session_id`, and broadcasts `{"type": "session_cleared"}`
- **AND** the server does NOT automatically spawn a greeting subprocess after clearing
- **AND** the client must send a fresh `{"type": "start"}` or `{"type": "message"}` to begin a new conversation

#### Scenario: Subprocess exits on its own
- **WHEN** the claude subprocess exits (context exhaustion, error)
- **THEN** the server sends `{"type": "error", "message": "Agent session ended"}` and closes the WebSocket connection with a descriptive close reason

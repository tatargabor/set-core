# Web Api Server Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.
## Requirements
### Requirement: Soniox API key endpoint
The server SHALL expose `GET /api/soniox-key` which returns the Soniox API key from the `SONIOX_API_KEY` environment variable. If the variable is not set, the endpoint SHALL return HTTP 404.

#### Scenario: Key configured
- **WHEN** `SONIOX_API_KEY` is set and a client requests `GET /api/soniox-key`
- **THEN** the response is `{ "api_key": "<value>" }` with HTTP 200

#### Scenario: Key not configured
- **WHEN** `SONIOX_API_KEY` is not set and a client requests `GET /api/soniox-key`
- **THEN** the response is HTTP 404 with `{ "error": "Soniox API key not configured" }`

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

### Requirement: Agent subprocess lifecycle management
The server SHALL maintain at most one agent subprocess per project. On server shutdown, all agent subprocesses SHALL be terminated via SIGTERM with a 5-second grace period before SIGKILL. Subprocess stderr SHALL be logged to the server log.

#### Scenario: Server shutdown with active agent
- **WHEN** the server receives SIGTERM while an agent subprocess is running
- **THEN** the agent subprocess receives SIGTERM, the server waits up to 5 seconds, then sends SIGKILL if still alive

#### Scenario: Orphan prevention
- **WHEN** the server starts
- **THEN** it does NOT attempt to adopt agent subprocesses from a previous server instance (clean start)

### Requirement: Stream-JSON event parsing
The server SHALL parse the claude subprocess stdout as newline-delimited JSON (stream-json format). Each parsed event SHALL be mapped to the chat WebSocket protocol and forwarded to the connected client. Unknown event types SHALL be forwarded as-is.

#### Scenario: Text content event
- **WHEN** the subprocess emits a text content event
- **THEN** the server sends `{ "type": "assistant_text", "content": "..." }` to the client

#### Scenario: Tool use event
- **WHEN** the subprocess emits a tool use event (e.g., Bash)
- **THEN** the server sends `{ "type": "tool_use", "tool": "Bash", "input": "..." }` to the client

#### Scenario: Response complete
- **WHEN** the subprocess emits a response complete event
- **THEN** the server sends `{ "type": "assistant_done" }` to the client

### Requirement: Coverage report endpoint
The server SHALL expose `GET /api/{project}/coverage-report` which reads and returns the content of `set/orchestration/spec-coverage-report.md` from the project directory.

#### Scenario: Report file exists
- **WHEN** the file `set/orchestration/spec-coverage-report.md` exists in the resolved project path
- **THEN** the endpoint returns `{"exists": true, "content": "<file content>"}` with HTTP 200

#### Scenario: Report file missing
- **WHEN** the file does not exist
- **THEN** the endpoint returns `{"exists": false}` with HTTP 200

#### Scenario: Invalid project
- **WHEN** the project name cannot be resolved
- **THEN** the endpoint returns HTTP 404


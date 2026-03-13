## ADDED Requirements

### Requirement: Chat message display
The orchestration chat SHALL display a scrollable message history with visually distinct user and agent messages. User messages SHALL be right-aligned with a different background color. Agent messages SHALL be left-aligned and support markdown rendering.

#### Scenario: Conversation flow
- **WHEN** user sends a message and the agent responds
- **THEN** the user message appears right-aligned and the agent response appears left-aligned below it

#### Scenario: Auto-scroll on new message
- **WHEN** a new agent message arrives and the user is scrolled to the bottom
- **THEN** the view auto-scrolls to show the new message

#### Scenario: Manual scroll preserved
- **WHEN** user has scrolled up to read earlier messages and a new message arrives
- **THEN** auto-scroll is paused and a "Jump to bottom" indicator appears

### Requirement: Agent output streaming
Agent responses SHALL stream in real-time as text arrives via WebSocket. Partial text SHALL appear incrementally (word by word or chunk by chunk) rather than waiting for the complete response.

#### Scenario: Streaming response
- **WHEN** the agent is generating a long response
- **THEN** text appears progressively in the message area, with a typing/thinking indicator

#### Scenario: Tool usage display
- **WHEN** the agent uses a tool (e.g., Bash, Read)
- **THEN** the tool invocation is shown as a collapsible block with the tool name and a summary of the input/output

### Requirement: Text input with send
The chat SHALL include a multi-line text input with a Send button. Pressing Enter SHALL send the message (Shift+Enter for newline). The input SHALL be disabled while the agent is processing.

#### Scenario: Send message
- **WHEN** user types a message and presses Enter
- **THEN** the message is sent to the agent via WebSocket, the input is cleared, and the input is disabled until the agent responds

#### Scenario: Multi-line input
- **WHEN** user presses Shift+Enter
- **THEN** a newline is inserted in the textarea (message is not sent)

#### Scenario: Input disabled during processing
- **WHEN** agent is processing (status: "thinking" or "responding")
- **THEN** the input and send button are disabled with a visual indicator

### Requirement: Agent session lifecycle
The chat SHALL manage the agent subprocess lifecycle. On first message, a session starts. The user SHALL be able to stop the current session and start a new one.

#### Scenario: First message starts session
- **WHEN** user sends the first message in the Orchestration tab
- **THEN** a WebSocket connection is established to `/ws/{project}/chat` and the message is sent

#### Scenario: Stop session
- **WHEN** user clicks the "New Session" button
- **THEN** the current agent subprocess is terminated, chat history is cleared, and a new session can begin

#### Scenario: Agent process exits
- **WHEN** the agent subprocess exits (context exhausted, error, or natural completion)
- **THEN** a "Session ended" message is displayed and the user can start a new session

### Requirement: Connection status indicator
The chat SHALL display a connection status indicator showing whether the WebSocket is connected, disconnected, or reconnecting.

#### Scenario: Connected
- **WHEN** WebSocket connection to `/ws/{project}/chat` is active
- **THEN** a green dot indicator is shown

#### Scenario: Disconnected
- **WHEN** WebSocket connection is lost
- **THEN** a red dot with "Disconnected" text is shown and auto-reconnect begins

### Requirement: Agent status indicator
The chat SHALL display the agent's current status: idle, thinking, responding, or using a tool.

#### Scenario: Agent thinking
- **WHEN** the server sends `{ "type": "status", "status": "thinking" }`
- **THEN** a "Thinking..." indicator with animation is shown below the message area

#### Scenario: Agent using tool
- **WHEN** the server sends a `tool_use` event
- **THEN** a "Running Bash..." or similar indicator is shown with the tool name

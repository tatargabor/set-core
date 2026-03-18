## ADDED Requirements

## IN SCOPE
- New "Sentinel" tab in wt-web Dashboard
- Event stream display (scrolling, color-coded by event type)
- Findings panel with severity badges and status
- Assessment section showing phase/run-level summaries
- Message input for sending messages to the sentinel
- Sentinel status bar (active/inactive, member name, uptime, PID)
- REST API endpoints for events, findings, status, and messaging
- 1s polling from frontend for near-real-time updates

## OUT OF SCOPE
- WebSocket streaming for sentinel events (1s REST polling is sufficient)
- Voice input for sentinel messages (existing voice input is for Agent tab only)
- Sentinel process management from wt-web (start/stop/restart — sentinel runs in terminal)
- Historical run browsing (only current run shown; archived runs accessed via filesystem)

### Requirement: Sentinel tab in Dashboard
The wt-web Dashboard SHALL include a "Sentinel" tab that displays sentinel event stream, findings, and allows message sending.

#### Scenario: Tab visible when sentinel data exists
- **WHEN** the user opens the Dashboard and `.wt/sentinel/status.json` exists
- **THEN** a "Sentinel" tab SHALL appear in the tab bar

#### Scenario: Tab shows inactive state
- **WHEN** the Sentinel tab is active but `status.json` shows `active: false` or `last_event_at` is older than 60 seconds
- **THEN** the status bar SHALL show "Sentinel not running" with the last activity timestamp

### Requirement: Event stream display
The Sentinel tab SHALL display the event stream from events.jsonl in a scrolling log view.

#### Scenario: Events rendered with type-specific styling
- **WHEN** events are displayed
- **THEN** each event type SHALL have distinct visual styling: poll (muted), crash (red), restart (orange), decision (green), escalation (yellow), finding (purple), message (blue)

#### Scenario: Auto-scroll to latest
- **WHEN** new events arrive via polling
- **THEN** the event stream SHALL auto-scroll to show the latest event (unless the user has scrolled up manually)

#### Scenario: Poll events condensed
- **WHEN** multiple consecutive poll events show the same state
- **THEN** they MAY be collapsed into a single line showing the count and time range (e.g., "12 polls, 14:20-14:23, state=running")

### Requirement: Findings panel
The Sentinel tab SHALL display current findings from findings.json.

#### Scenario: Findings displayed with severity badges
- **WHEN** findings exist
- **THEN** each finding SHALL be displayed with a severity badge (bug=red, observation=yellow, pattern=blue, regression=red+striped) and its status (open/fixed/dismissed)

#### Scenario: Empty state
- **WHEN** no findings exist
- **THEN** the panel SHALL show "No findings yet"

### Requirement: Message input
The Sentinel tab SHALL provide an input field for sending messages to the sentinel.

#### Scenario: Send message
- **WHEN** the user types a message and clicks Send (or presses Enter)
- **THEN** the message SHALL be sent via `POST /api/{project}/sentinel/message` and a `message_sent` event SHALL appear in the event stream

#### Scenario: Send disabled when sentinel inactive
- **WHEN** the sentinel is not active
- **THEN** the message input SHALL be disabled with placeholder "Sentinel not running"

### Requirement: REST API endpoints
The wt-web backend SHALL provide REST endpoints for sentinel data.

#### Scenario: GET events with since filter
- **WHEN** `GET /api/{project}/sentinel/events?since={ISO-timestamp}` is called
- **THEN** it SHALL return events from events.jsonl newer than the timestamp as a JSON array

#### Scenario: GET findings
- **WHEN** `GET /api/{project}/sentinel/findings` is called
- **THEN** it SHALL return the current findings.json content

#### Scenario: GET status
- **WHEN** `GET /api/{project}/sentinel/status` is called
- **THEN** it SHALL return status.json content with an added `is_active` computed field (true if `active: true` AND `last_event_at` within 60s)

#### Scenario: POST message
- **WHEN** `POST /api/{project}/sentinel/message` is called with `{"message": "text"}`
- **THEN** it SHALL write the message to the sentinel's inbox using the existing outbox file mechanism and return `{"status": "sent"}`

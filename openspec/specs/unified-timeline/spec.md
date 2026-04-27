# Unified Timeline

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Single chronological stream merging audit events and chat messages
- Three visual styles: system (centered/gray), user (right/blue), agent (left/gray)
- Chat input at the bottom for sending messages to investigation agent
- Audit icon mapping per action type
- Auto-scroll to newest entry
- System event condensation (collapse consecutive similar events)

### Out of scope
- Threads (flat timeline only)
- Message editing or deletion
- File/image attachments in chat
- Emoji reactions

## Requirements

### Requirement: Timeline construction
The timeline SHALL merge two data sources into one sorted array: audit log entries (as system events) and chat messages (as user/agent entries). Entries SHALL be sorted by timestamp ascending with newest at the bottom.

#### Scenario: Interleaved events
- **WHEN** the timeline has audit entries at 14:01, 14:03 and a chat message at 14:02
- **THEN** they appear in order: audit(14:01), chat(14:02), audit(14:03)

### Requirement: System event styling
System events SHALL be displayed centered, in muted gray color, with smaller font size. Each event SHALL have an icon mapped from its action type (e.g., "registered" → "●", "diagnosed" → "◆", "timeout_reminder" → "⏱").

#### Scenario: System event display
- **WHEN** an audit entry with action="diagnosed" is rendered
- **THEN** it shows centered: "── 14:03 · ◆ diagnosed · Confidence: 0.88 ──"

### Requirement: Chat message styling
User messages SHALL be right-aligned with a blue background. Agent messages SHALL be left-aligned with a gray background and a robot icon. Both SHALL show timestamp.

#### Scenario: User message display
- **WHEN** a user sends "Check the rate limiter too"
- **THEN** it appears right-aligned in a blue bubble with timestamp

### Requirement: Chat input
The timeline SHALL include a text input at the bottom with a Send button. Sending a message SHALL call POST /api/projects/{name}/issues/{id}/message and append the message to the timeline optimistically.

#### Scenario: Send chat message
- **WHEN** user types a message and clicks Send
- **THEN** the message appears immediately in the timeline (optimistic) and is sent to the API

#### Scenario: No investigation session
- **WHEN** user sends a message for an issue with no investigation_session
- **THEN** a new investigation session is created automatically with the investigation template context

### Requirement: Auto-scroll
The timeline SHALL auto-scroll to the bottom when new entries appear, unless the user has manually scrolled up. Scrolling up SHALL pause auto-scroll; scrolling to bottom SHALL resume it.

#### Scenario: New entry with auto-scroll
- **WHEN** a new audit entry appears and user is at the bottom
- **THEN** the timeline scrolls down to show the new entry

#### Scenario: User scrolled up
- **WHEN** user has scrolled up to read older entries and a new entry appears
- **THEN** the timeline does NOT auto-scroll (preserving user's position)

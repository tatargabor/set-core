## MODIFIED Requirements

### Requirement: Multi-channel notification dispatch
The system SHALL provide `send_notification(title, body, urgency, channels)` that dispatches notifications to configured channels. Channels are `"desktop"`, `"email"`, `"discord"`, or `"none"`. Urgency is `"normal"` or `"critical"`.

#### Scenario: Desktop notification
- **WHEN** channel includes `"desktop"` and `notify-send` is available
- **THEN** a desktop notification is sent via `notify-send` with the given urgency
- **AND** failures are logged but do not raise exceptions

#### Scenario: Email notification
- **WHEN** channel includes `"email"` and Resend API credentials are configured
- **THEN** an email is sent with HTML body including title, body, timestamp, and project name
- **AND** critical urgency messages get a `[CRITICAL]` subject prefix

#### Scenario: Discord notification
- **WHEN** channel includes `"discord"` and the Discord bot is connected
- **THEN** a message is posted to the project's Discord channel with an embed containing title, body, and urgency color
- **AND** critical urgency messages include the configured error mention

#### Scenario: Discord bot not connected
- **WHEN** channel includes `"discord"` but the bot is not connected
- **THEN** the discord channel is skipped silently (no error)
- **AND** a debug log message indicates Discord dispatch was skipped

#### Scenario: None channel
- **WHEN** channel is `"none"`
- **THEN** the notification is logged but not dispatched to any external service

#### Scenario: Missing notify-send
- **WHEN** channel includes `"desktop"` but `notify-send` is not installed
- **THEN** the desktop channel is skipped silently (no error)

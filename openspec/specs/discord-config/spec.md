# Discord Config Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Discord configuration section in orchestration.yaml
- Bot token via environment variable
- Guild ID and channel naming configuration
- Member-to-Discord-user mapping for @mentions
- Notification event filtering (which events trigger messages)

### Out of scope
- Discord bot creation wizard or OAuth2 setup flow
- Per-change or per-agent notification preferences
- Configuration UI in the web dashboard

## Requirements

### Requirement: Project-level Discord configuration
The system SHALL support a `discord:` section in `orchestration.yaml` for project-level Discord settings.

#### Scenario: Minimal configuration
- **WHEN** the config contains `discord: { enabled: true, guild_id: "123" }`
- **THEN** the bot connects to guild 123 and derives the channel name from the project name

#### Scenario: Full configuration
- **WHEN** the config contains guild_id, channel_name, notify_on, and mention_on_error
- **THEN** all values are used as specified

#### Scenario: Discord disabled by default
- **WHEN** no `discord:` section exists in orchestration.yaml
- **THEN** Discord integration is disabled (no bot connection attempted)

### Requirement: Bot token via environment
The system SHALL read the Discord bot token from the `SET_DISCORD_TOKEN` environment variable, never from config files.

#### Scenario: Token present
- **WHEN** `SET_DISCORD_TOKEN` is set in the environment
- **THEN** the bot uses it for authentication

#### Scenario: Token missing
- **WHEN** `discord.enabled` is `true` but `SET_DISCORD_TOKEN` is not set
- **THEN** an error is logged: "Discord enabled but SET_DISCORD_TOKEN not set"
- **AND** Discord integration is disabled for this session

### Requirement: Member-to-Discord mapping
The system SHALL support mapping set-core member identifiers to Discord user IDs for @mentions.

#### Scenario: Mapped member gets mentioned
- **WHEN** an error event occurs for a member whose Discord user ID is configured in `discord.member_map`
- **THEN** the Discord message includes an @mention for that user

#### Scenario: Unmapped member
- **WHEN** an error event occurs for a member not in `discord.member_map`
- **THEN** the message uses `mention_on_error` fallback (e.g., @role or @everyone)
- **AND** if no fallback is configured, no mention is added

### Requirement: Event filtering
The system SHALL allow configuring which events trigger Discord messages via `discord.notify_on`.

#### Scenario: Default events
- **WHEN** `discord.notify_on` is not specified
- **THEN** all event types are enabled: start, merge, stuck, complete, crash

#### Scenario: Filtered events
- **WHEN** `discord.notify_on` is set to `["start", "complete"]`
- **THEN** only run start and run complete events produce Discord messages
- **AND** intermediate events (merge, stuck) still update the thread embed but do not post to the main channel

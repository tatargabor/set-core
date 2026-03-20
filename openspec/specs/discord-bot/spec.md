## ADDED Requirements

## IN SCOPE
- Discord bot connection lifecycle (connect, disconnect, reconnect)
- Guild and channel resolution (find or create project channel)
- Thread creation and management per orchestration run
- Bot presence/status updates reflecting orchestration state
- Graceful shutdown on orchestration exit

## OUT OF SCOPE
- Slash commands or interactive Discord UI components
- User-to-agent chat via Discord (Layer 3 — future change)
- Discord OAuth2 flows or user authentication
- Multi-guild support (one guild per project)

### Requirement: Bot connection lifecycle
The system SHALL manage a Discord bot connection that starts with the orchestration API server and stops on shutdown.

#### Scenario: Bot connects on orchestration start
- **WHEN** the orchestration API server starts and `discord.enabled` is `true` in project config
- **THEN** the bot connects to Discord using the token from `SET_DISCORD_TOKEN` env var
- **AND** the bot sets its presence to "Watching <project-name>"

#### Scenario: Bot skipped when not configured
- **WHEN** the orchestration starts and `discord.enabled` is `false` or `SET_DISCORD_TOKEN` is unset
- **THEN** no Discord connection is attempted
- **AND** a debug log message indicates Discord is disabled

#### Scenario: Bot disconnects on shutdown
- **WHEN** the orchestration API server shuts down
- **THEN** the bot disconnects gracefully from Discord
- **AND** any pending message edits are flushed before disconnect

#### Scenario: Bot reconnects on connection loss
- **WHEN** the Discord WebSocket connection drops
- **THEN** the bot SHALL attempt reconnection using discord.py's built-in reconnect logic
- **AND** missed events during disconnection are replayed from the event bus backlog

### Requirement: Channel resolution
The system SHALL resolve or create a Discord text channel for each project.

#### Scenario: Existing channel found
- **WHEN** the bot connects and a channel named `#<project-name>` exists in the configured guild
- **THEN** the bot uses that channel for all project messages

#### Scenario: Channel auto-created
- **WHEN** the bot connects and no matching channel exists and the bot has `Manage Channels` permission
- **THEN** the bot creates a text channel named `#<project-name>` in the configured guild
- **AND** the channel topic is set to "set-core orchestration for <project-name>"

#### Scenario: Channel creation fails
- **WHEN** the bot lacks `Manage Channels` permission and no matching channel exists
- **THEN** the bot logs an error with instructions to create the channel manually or grant permission
- **AND** Discord notifications are disabled for this session

### Requirement: Thread management
The system SHALL create a Discord thread for each orchestration run within the project channel.

#### Scenario: Thread created on run start
- **WHEN** orchestration starts a new run
- **THEN** a thread is created in the project channel named "Run #<N> — <member-name> — <change-count> changes"
- **AND** the thread contains an initial status embed

#### Scenario: Thread auto-archives
- **WHEN** an orchestration run completes
- **THEN** the thread auto-archive duration is set to 24 hours
- **AND** a final summary embed is posted before archiving

#### Scenario: Existing thread reused on restart
- **WHEN** the orchestrator restarts (sentinel restart, crash recovery) for the same run
- **THEN** the bot finds the existing thread by run ID and resumes posting there
- **AND** a "Restarted" message is posted in the thread

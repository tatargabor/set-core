# Spec: discord-webhook

## IN SCOPE
- Discord webhook POST in notifications.py (replaces bot as primary)
- Webhook URL resolution: config.yaml → discord.json → env var
- Color-coded embeds (green/red/blue by urgency)
- Auto-enable discord channel when webhook URL available
- Template config.yaml webhook_url placeholder

## OUT OF SCOPE
- Discord bot removal (kept as fallback)
- set-web Discord integration changes
- Rate limiting
- Thread/channel management
- Interactive Discord commands

## ADDED Requirements

### Requirement: Webhook notification delivery

The orchestrator SHALL send Discord notifications via webhook POST when a webhook URL is configured.

#### Scenario: Webhook sends embed on merge
- WHEN `send_notification("change merged: auth", "25K tokens", urgency="normal", channels="discord")` is called
- AND a webhook URL is configured
- THEN a POST to the webhook URL SHALL contain an embed with green color and the title/body

#### Scenario: Critical notification uses red color
- WHEN urgency is "critical"
- THEN the embed color SHALL be red (0xE74C3C)

### Requirement: Webhook URL resolution

The system SHALL resolve the webhook URL from multiple sources in priority order.

#### Scenario: Config.yaml has webhook_url
- WHEN `discord.webhook_url` exists in the project's directives
- THEN that URL SHALL be used

#### Scenario: Global discord.json fallback
- WHEN no project-level webhook_url exists
- AND `~/.config/set-core/discord.json` contains `webhook_url`
- THEN that URL SHALL be used

#### Scenario: Environment variable fallback
- WHEN no config file has webhook_url
- AND `DISCORD_WEBHOOK_URL` env var is set
- THEN that URL SHALL be used

#### Scenario: No webhook configured
- WHEN no webhook URL is found from any source
- THEN the system SHALL fall back to the legacy bot-based Discord notification

### Requirement: Auto-enable discord channel

The system SHALL automatically include "discord" in notification channels when a webhook URL is available, without requiring explicit `channels="discord"` at each call site.

#### Scenario: Desktop-only call also goes to Discord
- WHEN `send_notification(title, body, channels="desktop")` is called
- AND a webhook URL is configured
- THEN the notification SHALL be sent to both desktop AND Discord

#### Scenario: No webhook means no auto-enable
- WHEN no webhook URL is configured
- THEN "discord" SHALL NOT be auto-added to channels

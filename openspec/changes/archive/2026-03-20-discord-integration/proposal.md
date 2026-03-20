# Discord Integration

## Why

Teams running parallel orchestration lack shared real-time visibility. Desktop notifications are local-only, email is slow, and the web dashboard requires each member to have it open. Discord is where teams already coordinate — putting orchestration events there gives instant, shared, persistent visibility with zero infrastructure beyond a bot token.

## What Changes

- **New**: Discord bot module that subscribes to the orchestration event bus and posts to Discord channels/threads
- **New**: Project-level Discord configuration in `orchestration.yaml`
- **New**: Discord as a notification channel alongside desktop and email
- **Modified**: `send_notification()` gains a `"discord"` channel option
- **Modified**: Orchestration startup/shutdown hooks to connect/disconnect the bot

## Capabilities

### New Capabilities

- `discord-bot`: Discord bot lifecycle — connect, disconnect, guild/channel resolution, thread management
- `discord-notifications`: Event-to-Discord mapping — which orchestration events produce which Discord messages, embed formatting, in-place updates
- `discord-config`: Project-level Discord configuration — guild ID, bot token, channel naming, member mapping, notification preferences

### Modified Capabilities

- `state-notifications`: Add `"discord"` as a supported notification channel in `send_notification()`

## Impact

- **New dependency**: `discord.py` (async, fits existing `asyncio` event loop)
- **Config**: New `discord:` section in `orchestration.yaml`
- **Environment**: `SET_DISCORD_TOKEN` env var for bot authentication
- **Existing code**: Minimal changes — `notifications.py` gains one new channel handler, event bus gains one new subscriber
- **No breaking changes**: Discord is opt-in, disabled by default

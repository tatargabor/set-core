# Proposal: discord-webhook-notifications

## Why

Discord notifications don't work because they depend on a Discord bot running inside set-web (FastAPI). The bot requires asyncio, discord.py library, and a running set-web process. In E2E runs, set-web may not be running, and even when it is, the bot initialization is fragile (Python version issues, import errors).

A Discord webhook is a simple HTTP POST — no bot, no set-web, no asyncio. The orchestrator engine already calls `send_notification()` at 8 call sites. Adding webhook support means notifications work out of the box.

## What Changes

- **Add** `_send_discord_webhook()` to `notifications.py` — simple `curl` POST to Discord webhook URL with embed formatting
- **Config**: read `webhook_url` from `discord` section in `config.yaml` directives, fallback to `~/.config/set-core/discord.json`
- **Replace** `_send_discord_sync()` (bot-based) with `_send_discord_webhook()` as primary Discord channel
- **Add** `discord` to default notification channels when webhook is configured
- **Update** web template `config.yaml` with `discord.webhook_url` placeholder

## Capabilities

### New Capabilities
- `discord-webhook`: Discord webhook notifications from orchestrator engine

### Modified Capabilities
(none)

## Impact

- `lib/set_orch/notifications.py` — replace bot-based `_send_discord_sync` with webhook POST
- `lib/set_orch/engine.py` — auto-enable discord channel when webhook configured
- `modules/web/set_project_web/templates/nextjs/wt/orchestration/config.yaml` — webhook_url placeholder

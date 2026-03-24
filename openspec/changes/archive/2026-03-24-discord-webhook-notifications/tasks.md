# Tasks: discord-webhook-notifications

## 1. Webhook URL resolution
- [x] 1.1 Add `_resolve_webhook_url()` to `notifications.py` — checks directives dict, then `~/.config/set-core/discord.json`, then `DISCORD_WEBHOOK_URL` env var
- [x] 1.2 Cache the resolved URL per process (module-level variable, resolve once)

## 2. Webhook POST implementation
- [x] 2.1 Add `_send_discord_webhook(url, title, body, urgency, project_name)` — curl POST with Discord embed JSON (color-coded by urgency)
- [x] 2.2 Replace `_send_discord_sync` call in `send_notification()` with webhook-first, bot-fallback logic

## 3. Auto-enable discord channel
- [x] 3.1 In `send_notification()`: if webhook URL is available and "discord" not in channels, auto-add it
- [x] 3.2 Pass directives to `send_notification()` or make URL resolution work without directives (global config fallback)

## 4. Template update
- [x] 4.1 Add `discord.webhook_url` placeholder (commented) to web template `config.yaml`

## 5. Tests
- [x] 5.1 Unit test: `_resolve_webhook_url()` priority order (directives → json → env)
- [x] 5.2 Unit test: `_send_discord_webhook()` builds correct embed JSON
- [x] 5.3 Unit test: auto-enable adds discord to channels when webhook configured

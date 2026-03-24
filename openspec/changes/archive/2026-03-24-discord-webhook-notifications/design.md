# Design: discord-webhook-notifications

## Decision 1: Webhook over bot

**Choice**: Use Discord webhook URL (simple HTTP POST) instead of discord.py bot.

**Rationale**: A webhook is a single `curl` call — no library dependency, no asyncio, no running server. The orchestrator engine runs in a bash/Python pipeline where sync HTTP is natural. The bot approach requires set-web running, discord.py installed, and an asyncio event loop — all fragile in the E2E context.

## Decision 2: Config resolution

**Choice**: Resolve webhook URL from (in priority order):
1. `discord.webhook_url` in directives (from `config.yaml`)
2. `webhook_url` in `~/.config/set-core/discord.json`
3. `DISCORD_WEBHOOK_URL` env var

**Rationale**: Project-specific webhook (different channel per project) via config.yaml. Global fallback via discord.json (same file the bot uses). Env var for CI/containers.

## Decision 3: Embed format

**Choice**: Discord embed with color-coded urgency:
- Green (0x2ECC71) — normal (merge, complete)
- Red (0xE74C3C) — critical (failed, stuck)
- Blue (0x3498DB) — info (start)

```json
{
  "embeds": [{
    "title": "change merged: contact-form",
    "description": "Tokens: 25K | Verify retries: 0",
    "color": 3066993,
    "footer": {"text": "micro-web-run6"}
  }]
}
```

## Decision 4: Keep bot code as fallback

**Choice**: Keep `_send_discord_sync()` but try webhook first. If webhook URL not configured, fall back to bot. If neither works, log and skip.

```python
def _send_discord(title, body, urgency, project_name):
    url = _resolve_webhook_url()
    if url:
        _send_discord_webhook(url, title, body, urgency, project_name)
    else:
        _send_discord_sync(title, body, urgency, project_name)  # legacy bot
```

## Decision 5: Auto-enable discord channel

**Choice**: In `send_notification()`, if `channels` doesn't include "discord" but a webhook URL is configured, automatically add it. This way existing `send_notification("title", "body", channels="desktop")` calls also go to Discord without changing every call site.

Alternative: require explicit `channels="desktop,discord"` at each call site — rejected because it requires touching 8 call sites and the whole point is zero-config.

## Decision 6: Rate limiting

**Choice**: No rate limiting for now. Discord webhooks have a 30 req/min limit. The orchestrator sends ~5-10 notifications per run (start, merges, complete). Well within limits.

Future: if needed, add a simple timestamp check (min 5s between messages).

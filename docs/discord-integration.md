# Discord Integration

Real-time orchestration status updates in Discord with thread-per-run organization.

## Setup

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" → name it (e.g., "SET Orchestrator")
3. Go to **Bot** tab → click "Add Bot"
4. Copy the **bot token**
5. Under **Privileged Gateway Intents**, enable:
   - Server Members Intent (optional, for member display)
6. Under **Bot Permissions**, select:
   - Send Messages
   - Send Messages in Threads
   - Create Public Threads
   - Embed Links
   - Read Message History
   - Manage Channels (optional — for auto-creating project channels)

### 2. Invite Bot to Your Server

Generate an invite URL from **OAuth2 → URL Generator**:
- Scopes: `bot`
- Permissions: (select the same as step 1.6)

Open the URL to invite the bot to your Discord server.

### 3. Get Your Guild ID

1. Enable Developer Mode in Discord (Settings → App Settings → Advanced → Developer Mode)
2. Right-click your server name → "Copy Server ID"

### 4. Configure set-core

Add to your `orchestration.yaml`:

```yaml
discord:
  enabled: true
  guild_id: "YOUR_GUILD_ID"
  # channel_name: "my-project"   # optional, defaults to project name
  # notify_on:                   # optional, defaults to all
  #   - start
  #   - merge
  #   - stuck
  #   - complete
  #   - crash
  # mention_on_error: "@oncall"  # optional, who to ping on errors
  # member_map:                  # optional, set-core member → Discord user ID
  #   "user@hostname": "DISCORD_USER_ID"
```

Set the bot token as an environment variable (never in config files):

```bash
export SET_DISCORD_TOKEN="your-bot-token-here"
```

### 5. Install discord.py

```bash
pip install 'set-core[discord]'
```

## How It Works

When orchestration starts with Discord enabled:

1. **Bot connects** to Discord and finds/creates the project channel
2. **Each run** gets a Discord thread (e.g., "Run #5 — user@host — 8 changes")
3. **Live status embed** in the thread updates every 30 seconds showing per-change progress
4. **Main channel** gets one-line summaries: start, merge, error, complete
5. **Errors** trigger @mentions for the affected team member

```
#my-project (main channel)
├─ 🟢 user@host started Run #5 (8 changes)
├─ ✅ user@host: add-auth merged
├─ ❌ user@host: fix-cart — merge conflict  @user
├─ 📊 user@host Run #5 done: 7/8 merged
│
├─ 🧵 Thread: Run #5 — user@host — 8 changes
│   └─ [Live embed with per-change progress bars]
```

## Configuration Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable Discord integration |
| `guild_id` | string | required | Discord server ID |
| `channel_name` | string | project name | Channel name (auto-created if missing) |
| `notify_on` | list | all events | Which events post to main channel |
| `mention_on_error` | string | none | Who to @mention on errors |
| `member_map` | dict | `{}` | Map set-core members to Discord user IDs |

## Troubleshooting

**Bot doesn't connect**: Check `SET_DISCORD_TOKEN` is set and valid.

**Channel not found**: Ensure `guild_id` is correct and the bot is a member of the server. Grant `Manage Channels` permission for auto-creation.

**No messages appearing**: Check `notify_on` filter. Thread embeds always update regardless of filter.

**Rate limiting**: The bot throttles embed edits to once per 30 seconds. If you see 429 errors, the throttle will automatically back off.

# Discord Integration — Design

## Context

set-core orchestration currently supports desktop and email notifications. Teams using set-core across multiple machines coordinate via git-based team-sync. There is no shared real-time feed of orchestration activity visible to all team members without each running the web dashboard independently.

The orchestration system already has:
- An event bus (`events.py`) with `subscribe()` for in-process handlers
- A notification dispatcher (`notifications.py`) with pluggable channels
- A FastAPI/uvicorn API server running during orchestration
- Per-agent activity files (`activity.json`) with progress data
- WebSocket push for the web dashboard

Discord.py is async-native and integrates cleanly with the existing asyncio event loop.

## Goals / Non-Goals

**Goals:**
- Add Discord as a notification channel with thread-per-run visibility
- Run the bot in-process with the API server (no separate daemon)
- Provide live-updating status embeds in run threads
- Support @mentions on errors for the right team member

**Non-Goals:**
- Interactive Discord commands or slash commands (future Layer 3)
- Webhook-only mode without a bot (possible future simplification)
- Discord-based agent chat or task assignment
- Multi-guild support

## Decisions

### D1: In-process bot (same asyncio loop as uvicorn)

The Discord bot runs as a background task in the same asyncio event loop as the FastAPI server. No separate process, no IPC.

**Why over separate process:** Simpler deployment, shared state (event bus subscriptions, config), no serialization overhead. discord.py's `Client` is designed for async coexistence.

**Risk:** Bot crash could affect the API server. Mitigation: wrap the bot in a supervisor task that catches exceptions and logs them without propagating.

### D2: Event bus subscriber pattern

The bot registers a handler via `events.subscribe(type=None, handler=on_event)` to receive all events. The handler routes events to the appropriate Discord action (embed update, channel message, thread creation).

**Why over polling:** Zero latency, no wasted cycles. The event bus already supports this pattern.

### D3: Thread per run, embed per thread

Each orchestration run creates one Discord thread. Inside the thread, a single embed message is maintained and edited in-place to show current status. Main channel gets one-liner summaries only.

**Why threads:** Prevents channel spam when multiple runs overlap. Discord threads auto-archive. Each run's history is self-contained and searchable.

**Why single-embed edit:** Discord rate limits (5 msg/5sec/channel). Editing one message uses 1 API call vs posting N messages. Progress changes are frequent — edits absorb the volume.

### D4: 30-second update throttle

Embed edits are throttled to at most once per 30 seconds. Events arriving within the window are batched — the next edit reflects all accumulated changes.

**Why 30s:** Discord rate limit is 5/5s per channel, but threads count separately. 30s gives comfortable margin, avoids 429 responses, and is fast enough for human observation.

### D5: Config in orchestration.yaml, token in env

Discord settings (guild_id, channel_name, notify_on, member_map) live in `orchestration.yaml` (committed, shared). The bot token lives in `SET_DISCORD_TOKEN` env var (never committed).

**Why split:** Guild ID and preferences are team-shared config. Bot tokens are secrets that vary per environment.

### D6: Channel auto-creation with fallback

The bot tries to find `#<project-name>` in the guild. If missing and bot has `Manage Channels` permission, it creates it. If it can't create, it logs an error and disables Discord for the session.

**Why auto-create:** Zero-setup experience for new projects. The fallback ensures the bot degrades gracefully without permissions.

## Prior Art (MIT licensed, patterns adopted)

Three existing open-source projects were evaluated. Key patterns adopted from each:

### From OpenSwarm (Intrect-io/OpenSwarm)
- **Typed event hub with replay buffers**: EventEmitter with typed `HubEvent` union and category-specific replay buffers (500 events general, 300 logs, 200 stages). Adopted pattern: our event bus `subscribe()` already does this — Discord module is just another subscriber, keeping it fully optional and swappable (could be Slack, Telegram, etc. later).
- **Graceful shutdown order**: Reverse-init teardown — flush pending Discord edits before disconnect, disconnect before shutting down the API server.

### From zebbern/claude-code-discord
- **SessionThreadManager**: Clean run→thread mapping with auto-archive (24h), restart reuse via run ID lookup, stale cleanup with configurable thresholds. Thread names sanitized and truncated to 80 chars. Adopted directly for our `ThreadManager`.
- **Code-block-aware message splitting**: `splitMessage()` preserves markdown code fences across Discord's 2000-char limit by reopening fences. ANSI escape stripping for CLI output. Adopted for our `embeds.py` formatting utilities.

### From chadingTV/claudecode-discord
- **Throttled streaming edits (1.5s)**: Output buffer with throttled Discord message edits prevents rate limiting. Adopted but adjusted to 30s for our use case (status embeds change less frequently than streaming output).
- **Heartbeat "still working..." updates**: 15-second heartbeats showing elapsed time and tool usage while agent is active. Adopted for long-running change progress.
- **Exponential backoff reconnect**: 5s → 10s → 15s → steady 30s intervals on connection loss. Adopted for our bot reconnection logic.

### Patterns explicitly NOT adopted
- Slash commands and interactive buttons (Layer 3 — future)
- Linear/task management integration (too tightly coupled to OpenSwarm)
- SQLite session persistence (our event bus JSONL is sufficient)
- Deno runtime patterns (we use Python/discord.py)
- Channel-per-project fixed mapping (we use auto-create with fallback)

## Risks / Trade-offs

- **[Discord.py maintenance]** → discord.py is actively maintained again (post-2022 return). If it stalls, `hikari` is a drop-in alternative with similar async API.
- **[Bot token management]** → Teams must create a Discord application and bot. This is a one-time setup but adds onboarding friction. Mitigation: clear docs + `set-project init` prints setup instructions.
- **[Rate limiting under heavy load]** → Many concurrent runs × frequent state changes could hit limits even with throttling. Mitigation: per-thread throttle + exponential backoff on 429 responses.
- **[In-process crash isolation]** → A discord.py bug could affect orchestration. Mitigation: supervisor task with exception boundary + optional `discord.enabled: false` kill switch.

## Architecture

```
┌──────────────────────────── uvicorn process ─────────────────────────────┐
│                                                                           │
│  FastAPI app                        DiscordBot (background task)          │
│  ├─ /ws/{project}/stream            ├─ discord.Client                    │
│  ├─ /api/{project}/state            ├─ event_bus.subscribe(on_event)     │
│  └─ /api/{project}/...              ├─ ThreadManager (run_id → thread)   │
│                                     ├─ EmbedThrottle (30s batch)         │
│                                     └─ ChannelResolver (find/create)     │
│                                                                           │
│  Event Bus (events.py)                                                    │
│  ├─ emit(STATE_CHANGE, ...) ──────────▶ on_event() ──▶ embed update      │
│  ├─ emit(MERGE_ATTEMPT, ...) ────────▶ on_event() ──▶ channel msg        │
│  └─ emit(SENTINEL_RESTART, ...) ─────▶ on_event() ──▶ channel alert     │
│                                                                           │
│  notifications.py                                                         │
│  └─ send_notification(..., channels=["discord"]) ──▶ _send_discord()     │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
lib/set_orch/discord/
├─ __init__.py          # DiscordBot class, start/stop
├─ channel.py           # ChannelResolver — find or create project channel
├─ threads.py           # ThreadManager — run_id ↔ thread mapping
├─ embeds.py            # Embed builders — status, summary, error
├─ throttle.py          # EmbedThrottle — 30s batching
└─ events.py            # Event handler — routes bus events to Discord actions
```

## Open Questions

- Should we also support a webhook-only mode (no bot, just HTTP POST) for teams that don't want to run a bot? This would be Layer 1 only (no threads, no embeds, no edits) but zero-process.
- Should thread names include a short hash of the run for uniqueness, or is `Run #N — member` sufficient?
